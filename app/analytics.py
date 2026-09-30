from __future__ import annotations

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "analytics.sqlite"

EVENT_TYPES = ("page_view", "add_to_cart", "begin_checkout", "purchase")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY,
  ts          TEXT    NOT NULL,
  session_id  TEXT    NOT NULL,
  locale      TEXT    NOT NULL,
  path        TEXT    NOT NULL,
  event_type  TEXT    NOT NULL,
  sku         TEXT,
  revenue_chf REAL,
  referrer    TEXT,
  device      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_path   ON events(path);
CREATE INDEX IF NOT EXISTS idx_events_locale ON events(locale);
CREATE INDEX IF NOT EXISTS idx_events_ts     ON events(ts);
"""


def connect(path: pathlib.Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record(
    conn: sqlite3.Connection,
    *,
    ts: str,
    session_id: str,
    locale: str,
    path: str,
    event_type: str,
    sku: str | None = None,
    revenue_chf: float | None = None,
    referrer: str | None = None,
    device: str | None = None,
) -> None:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}")
    conn.execute(
        "INSERT INTO events (ts, session_id, locale, path, event_type, sku, revenue_chf,"
        " referrer, device) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, session_id, locale, path, event_type, sku, revenue_chf, referrer, device),
    )
    conn.commit()


def top_paths(conn: sqlite3.Connection, limit: int = 12) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT path, COUNT(*) AS views"
        " FROM events WHERE event_type = 'page_view'"
        " GROUP BY path ORDER BY views DESC LIMIT ?",
        (limit,),
    ).fetchall()


def locale_funnel(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT locale,"
        " COUNT(DISTINCT session_id) AS sessions,"
        " COUNT(DISTINCT CASE WHEN event_type='add_to_cart' THEN session_id END) AS carts,"
        " COUNT(DISTINCT CASE WHEN event_type='begin_checkout' THEN session_id END)"
        "   AS checkouts,"
        " COUNT(DISTINCT CASE WHEN event_type='purchase' THEN session_id END) AS purchases"
        " FROM events GROUP BY locale ORDER BY sessions DESC"
    ).fetchall()


def revenue_by_locale(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT locale, COALESCE(SUM(revenue_chf), 0) AS revenue,"
        " COUNT(*) FILTER (WHERE event_type = 'purchase') AS orders"
        " FROM events GROUP BY locale ORDER BY revenue DESC"
    ).fetchall()