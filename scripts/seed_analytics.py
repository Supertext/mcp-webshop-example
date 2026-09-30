"""Generate 30 days of deterministic analytics: a fixed RNG seed, so every run
writes the same events."""

from __future__ import annotations

import datetime
import pathlib
import random
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.analytics import DB_PATH, connect, init_db  # noqa: E402
from app.catalog import PRODUCTS  # noqa: E402

SEED = 20260831
DAYS = 30
SESSIONS = 9_000

LOCALE_WEIGHTS = {"de-CH": 0.46, "en": 0.25, "fr-CH": 0.21, "it-CH": 0.08}

# Where sessions land.
ENTRY_WEIGHTS = {"home": 0.34, "guide": 0.30, "product": 0.22, "category": 0.14}

# Product page views.
VIEW_WEIGHTS = {
    "arv-p240": 0.26, "clb-k2": 0.14, "arv-tx3": 0.13, "clb-cr12": 0.11,
    "arv-s1": 0.11, "clb-r94": 0.10, "clb-vf1": 0.09, "arv-ab30": 0.06,
}

# Purchases by product.
BUY_WEIGHTS = {
    "arv-tx3": 0.26, "arv-ab30": 0.17, "clb-vf1": 0.12, "clb-cr12": 0.11,
    "clb-r94": 0.11, "clb-k2": 0.10, "arv-s1": 0.08, "arv-p240": 0.05,
}

# Long-form bounce and purchase rate, per locale.
BOUNCE_LONGFORM = {"fr-CH": 0.62, "it-CH": 0.35, "de-CH": 0.31, "en": 0.30}
PURCHASE_RATE = {"de-CH": 0.034, "en": 0.031, "it-CH": 0.028, "fr-CH": 0.016}

# Share of sessions that open a legal page.
LEGAL_VISIT_RATE = 0.006
LEGAL_SLUGS = ("terms", "returns", "warranty", "privacy", "shipping")

REFERRERS = ("organic", "direct", "paid", "social")
REFERRER_WEIGHTS = (0.52, 0.26, 0.14, 0.08)


def _pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def seed(path: pathlib.Path = DB_PATH) -> int:
    rng = random.Random(SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = connect(path)
    init_db(conn)

    end = datetime.datetime.now(datetime.UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = end - datetime.timedelta(days=DAYS)
    rows: list[tuple] = []
    count = 0

    for _ in range(SESSIONS):
        session_id = uuid.UUID(int=rng.getrandbits(128)).hex
        locale = _pick(rng, LOCALE_WEIGHTS)
        device = "mobile" if rng.random() < 0.58 else "desktop"
        referrer = rng.choices(REFERRERS, weights=REFERRER_WEIGHTS, k=1)[0]
        moment = start + datetime.timedelta(
            seconds=rng.randrange(int((end - start).total_seconds()))
        )

        elapsed = 0

        # Loop variables are bound as defaults (evaluated at definition time, in
        # this same iteration) to satisfy ruff B023; emit never outlives the loop.
        def emit(
            rel_path,
            event_type,
            sku=None,
            revenue=None,
            _moment=moment,
            _session_id=session_id,
            _locale=locale,
            _referrer=referrer,
            _device=device,
        ):
            nonlocal count, elapsed
            elapsed += rng.randrange(20, 180)
            ts = (_moment + datetime.timedelta(seconds=elapsed)).isoformat(
                timespec="seconds"
            )
            rows.append((ts, _session_id, _locale, rel_path, event_type, sku, revenue,
                         _referrer, _device))
            count += 1

        entry = _pick(rng, ENTRY_WEIGHTS)
        if entry == "home":
            emit("/", "page_view")
        elif entry == "guide":
            emit("/guide/avalanche-basics", "page_view")
            if rng.random() < BOUNCE_LONGFORM[locale]:
                continue
        elif entry == "category":
            emit(f"/c/{rng.choice(['avalanche-safety', 'climbing'])}", "page_view")
        else:
            emit(f"/p/{_pick(rng, VIEW_WEIGHTS)}", "page_view")

        for _ in range(rng.randrange(1, 5)):
            sku = _pick(rng, VIEW_WEIGHTS)
            emit(f"/p/{sku}", "page_view")

        if rng.random() < LEGAL_VISIT_RATE:
            emit(f"/legal/{rng.choice(LEGAL_SLUGS)}", "page_view")

        if rng.random() < PURCHASE_RATE[locale] * 3.0:
            sku = _pick(rng, BUY_WEIGHTS)
            emit(f"/p/{sku}", "add_to_cart", sku=sku)
            emit("/cart", "page_view")
            if rng.random() < 0.62:
                emit("/checkout", "page_view")
                emit("/checkout", "begin_checkout")
                if rng.random() < 0.55:
                    emit("/checkout", "purchase", sku=sku,
                         revenue=float(PRODUCTS[sku].price_chf))

    rows.sort(key=lambda r: r[0])
    conn.executemany(
        "INSERT INTO events (ts, session_id, locale, path, event_type, sku, revenue_chf,"
        " referrer, device) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return count


if __name__ == "__main__":
    total = seed()
    print(f"Seeded {total:,} events into {DB_PATH}")
