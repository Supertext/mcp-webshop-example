from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import pathlib

import markupsafe

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "content" / "source.en.json"
LOCALES_DIR = ROOT / "locales"

DEFAULT_LOCALE = "en"
TARGET_LOCALES = ("de-CH", "fr-CH", "it-CH")

CONTENT_CLASSES = frozenset({
    "ui_chrome",
    "marketing",
    "product_prose",
    "product_spec",
    "safety_critical",
    "legal",
    "certification",
    "transactional",
})

POLICIES = frozenset({"human_only"})

_REQUIRED_FIELDS = ("text", "class", "surfaces", "translatable")


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def load_source(path: pathlib.Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    strings = data.get("strings")
    if not isinstance(strings, dict):
        raise ValueError(f"{path}: 'strings' must be an object")

    for key, entry in strings.items():
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                raise ValueError(f"{path}: '{key}' missing required field '{field}'")
        if entry["class"] not in CONTENT_CLASSES:
            raise ValueError(f"{path}: '{key}' has unknown class '{entry['class']}'")
        policy = entry.get("policy")
        if policy is not None and policy not in POLICIES:
            raise ValueError(f"{path}: '{key}' has unknown policy '{policy}'")
        if not isinstance(entry["surfaces"], list):
            raise ValueError(f"{path}: '{key}' surfaces must be a list")
        if not isinstance(entry["translatable"], bool):
            raise ValueError(f"{path}: '{key}' translatable must be a boolean")

    return data


@dataclasses.dataclass(frozen=True)
class Resolved:
    text: str
    state: str


def load_catalog(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "locale": path.stem, "strings": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(
    source: dict, catalogs: dict[str, dict], key: str, locale: str
) -> Resolved:
    meta = source["strings"][key]
    src = meta["text"]

    if not meta["translatable"]:
        return Resolved(src, "source_locked")

    if locale == DEFAULT_LOCALE:
        return Resolved(src, "source")

    entry = catalogs.get(locale, {}).get("strings", {}).get(key)
    if entry is None:
        return Resolved(src, "fallback")

    fresh = entry["source_hash"] == short_hash(src)

    if meta.get("policy") == "human_only" and not (entry["state"] == "verified" and fresh):
        return Resolved(src, "withheld")

    if not fresh:
        return Resolved(entry["text"], "stale")

    return Resolved(entry["text"], entry["state"])


class Catalogs:
    """Source and locale catalogues, re-read whenever a file's mtime or size changes.

    Cheap enough to call refresh() on every request: four pathlib stat calls.
    """

    def __init__(
        self,
        source_path: pathlib.Path = SOURCE_PATH,
        locales_dir: pathlib.Path = LOCALES_DIR,
        locales: tuple[str, ...] = TARGET_LOCALES,
    ) -> None:
        self.source_path = source_path
        self.locales_dir = locales_dir
        self.locale_names = locales
        self.source: dict = {"schema_version": 1, "default_locale": "en", "strings": {}}
        self.locales: dict[str, dict] = {}
        self.version = ""
        self._fingerprint: tuple | None = None

    def _paths(self) -> list[pathlib.Path]:
        return [self.source_path] + [self.locales_dir / f"{n}.json" for n in self.locale_names]

    def _current_fingerprint(self) -> tuple:
        parts = []
        for path in self._paths():
            try:
                stat = path.stat()
                parts.append((str(path), stat.st_mtime_ns, stat.st_size))
            except FileNotFoundError:
                parts.append((str(path), 0, 0))
        return tuple(parts)

    def refresh(self) -> None:
        fingerprint = self._current_fingerprint()
        if fingerprint == self._fingerprint:
            return
        self.source = load_source(self.source_path)
        self.locales = {
            name: load_catalog(self.locales_dir / f"{name}.json") for name in self.locale_names
        }
        self._fingerprint = fingerprint
        self.version = short_hash(repr(fingerprint))

    def resolve(self, key: str, locale: str) -> Resolved:
        return resolve(self.source, self.locales, key, locale)


CATALOGS = Catalogs()


STATE_MARKERS = {
    "verified": "✓",
    "machine": "MT",
    "pending": "⏱",
    "stale": "!",
    "withheld": "EN",
    "fallback": "EN",
    "source": "—",
    "source_locked": "\U0001f512",
}


def render_string(catalogs: Catalogs, key: str, locale: str, trust: bool) -> markupsafe.Markup:
    resolved = catalogs.resolve(key, locale)
    text = markupsafe.escape(resolved.text)
    classes = "s trust" if trust else "s"
    marker = ""
    if trust:
        marker = f'<sup class="m">{markupsafe.escape(STATE_MARKERS[resolved.state])}</sup>'
    return markupsafe.Markup(
        f'<span class="{classes}" data-state="{resolved.state}">{text}{marker}</span>'
    )


def render_notice(catalogs: Catalogs, key: str, locale: str) -> markupsafe.Markup:
    """Spec 5.3: a human_only string that is not yet verified shows English plus an
    explicit notice, so an unverified liability paragraph is never presented as a
    translation. Empty markup for every other resolved state."""
    if catalogs.resolve(key, locale).state != "withheld":
        return markupsafe.Markup("")
    title = markupsafe.escape(catalogs.resolve("notice.withheld.title", locale).text)
    body = markupsafe.escape(catalogs.resolve("notice.withheld.body", locale).text)
    return markupsafe.Markup(
        f'<aside class="withheld-notice"><b>{title}</b><span>{body}</span></aside>'
    )


def state_counts(catalogs: Catalogs, keys: list[str], locale: str) -> dict[str, int]:
    counter: collections.Counter[str] = collections.Counter()
    for key in keys:
        counter[catalogs.resolve(key, locale).state] += 1
    return dict(counter)
