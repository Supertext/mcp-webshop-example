"""Machine-translate the whole shop through the Supertext public API.

    make translate                 # all three locales
    make translate LOCALE=fr-CH    # one locale
    python scripts/translate.py --quote   # price it, translate nothing

Every translatable string in content/source.en.json is sent to
POST /translate/ai/text (batched, so the whole shop is ~15 requests) and
written to locales/<locale>.json as state "machine" with engine
"supertext-api". Strings with translatable: false are skipped, and existing
entries in states pending/verified are left alone — this script fills gaps and
refreshes machine output; it never overwrites a human.

Auth: SUPERTEXT_API_KEY in the environment or in ./.env (gitignored). The
value is the bare token from the cockpit; the "Supertext-Auth-Key" scheme is
added here.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.i18n import LOCALES_DIR, SOURCE_PATH, TARGET_LOCALES, short_hash  # noqa: E402

API = "https://api.supertext.com/v1"
ENGINE = "supertext-api"
SOURCE_LANG = "en"
# Endpoint limits per the OpenAPI spec: 10,000 chars/request, 5 req/s.
# Pack below the ceiling so a long legal body never tips a batch over, and
# keep at most 5 requests in flight: a full locale is 5 batches, so one
# locale goes out as a single burst. A 9,000-char batch takes the API ~15 s
# serially; in parallel the whole shop lands in about that.
BATCH_CHARS = 9_000
PARALLEL = 5


def api_key() -> str:
    key = os.environ.get("SUPERTEXT_API_KEY")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("SUPERTEXT_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        sys.exit(
            "SUPERTEXT_API_KEY is not set (env or ./.env). Get one from the Supertext cockpit."
        )
    return key


def headers() -> dict[str, str]:
    return {"Authorization": f"Supertext-Auth-Key {api_key()}", "Content-Type": "application/json"}


def load_source() -> dict[str, dict]:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))["strings"]


def load_locale(locale: str) -> dict:
    path = LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {"schema_version": 1, "locale": locale, "strings": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_locale(locale: str, data: dict) -> None:
    """Atomic: the site hot-reloads these files mid-poll."""
    path = LOCALES_DIR / f"{locale}.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def pending_keys(source: dict[str, dict], catalog: dict, force: bool) -> list[str]:
    """Keys that need machine output. Skips untranslatable strings and never
    touches a pending or verified entry; a fresh machine entry is skipped
    unless --force."""
    keys = []
    for key, meta in source.items():
        if not meta["translatable"]:
            continue
        entry = catalog["strings"].get(key)
        if entry is None:
            keys.append(key)
            continue
        if entry["state"] in ("pending", "verified"):
            continue
        if force or entry["source_hash"] != short_hash(meta["text"]):
            keys.append(key)
    return keys


def batches(source: dict[str, dict], keys: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] = []
    size = 0
    for key in keys:
        n = len(source[key]["text"])
        if cur and size + n > BATCH_CHARS:
            out.append(cur)
            cur, size = [], 0
        cur.append(key)
        size += n
    if cur:
        out.append(cur)
    return out


def call(client: httpx.Client, path: str, texts: list[str], locale: str) -> dict:
    body = {"text": texts, "source_lang": SOURCE_LANG, "target_lang": locale}
    for attempt in range(4):
        r = client.post(f"{API}{path}", headers=headers(), json=body, timeout=60)
        if r.status_code == 429 and attempt < 3:
            time.sleep(1.0 * (attempt + 1))
            continue
        if r.status_code != 200:
            sys.exit(f"{path} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("unreachable")


def quote(source: dict[str, dict], locales: list[str]) -> None:
    total_chf = 0.0
    total_chars = 0
    with httpx.Client() as client:
        for locale in locales:
            keys = pending_keys(source, load_locale(locale), force=True)
            chf = chars = 0.0
            for group in batches(source, keys):
                texts = [source[k]["text"] for k in group]
                q = call(client, "/translate/ai/text/quote", texts, locale)
                chf += q["prices"]["chf"]
                chars += q["character_count"]
            print(f"{locale}: {len(keys)} strings, {int(chars):,} chars, CHF {chf:.2f}")
            total_chf += chf
            total_chars += chars
    print(f"total: {int(total_chars):,} chars, CHF {total_chf:.2f} (machine translation only)")


def translate(source: dict[str, dict], locales: list[str], force: bool) -> None:
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    with httpx.Client() as client:
        for locale in locales:
            catalog = load_locale(locale)
            keys = pending_keys(source, catalog, force)
            if not keys:
                print(f"{locale}: nothing to do")
                continue
            groups = batches(source, keys)
            t0 = time.perf_counter()

            def one(group: list[str], loc: str = locale) -> tuple[list[str], list[str]]:
                # `loc` bound at definition time: the closure is created per locale
                texts = [source[k]["text"] for k in group]
                result = call(client, "/translate/ai/text", texts, loc)
                translated = result["translated_text"]
                if len(translated) != len(texts):
                    sys.exit(f"{loc}: sent {len(texts)} segments, got {len(translated)} back")
                return group, translated

            done = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL) as pool:
                for group, translated in pool.map(one, groups):
                    for key, text in zip(group, translated, strict=True):
                        catalog["strings"][key] = {
                            "text": text,
                            "state": "machine",
                            "source_hash": short_hash(source[key]["text"]),
                            "engine": ENGINE,
                            "updated_at": now,
                        }
                    done += len(group)
                    # write after every batch so the page fills in as it goes
                    save_locale(locale, catalog)
                    print(f"{locale}: {done}/{len(keys)}", flush=True)
            elapsed = time.perf_counter() - t0
            print(f"{locale}: {len(keys)} strings in {len(groups)} requests, {elapsed:.1f}s")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--locale", action="append", choices=TARGET_LOCALES, help="repeatable; default all"
    )
    p.add_argument(
        "--quote", action="store_true", help="price the job and exit; translates nothing"
    )
    p.add_argument(
        "--force", action="store_true", help="re-translate fresh machine entries too"
    )
    a = p.parse_args()
    locales = a.locale or list(TARGET_LOCALES)
    source = load_source()
    if a.quote:
        quote(source, locales)
    else:
        translate(source, locales, a.force)


if __name__ == "__main__":
    main()
