"""The seeded analytics are shaped on purpose: the skews are the workshop's
argument. Do not "fix" the weights in scripts/seed_analytics.py; these
tests pin the shape."""

import pytest

from app.analytics import connect
from scripts.seed_analytics import seed


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("seed") / "analytics.sqlite"
    seed(path)
    return connect(path)


def _views(conn, path):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE event_type='page_view' AND path=?", (path,)
    ).fetchone()
    return row["n"]


def _revenue(conn, sku):
    row = conn.execute(
        "SELECT COALESCE(SUM(revenue_chf), 0) AS r FROM events WHERE sku=? AND"
        " event_type='purchase'", (sku,)
    ).fetchone()
    return row["r"]


def test_seed_is_deterministic(tmp_path):
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    assert seed(a) == seed(b)
    rows_a = connect(a).execute(
        "SELECT session_id, locale, path, event_type, sku, revenue_chf, referrer,"
        " device FROM events ORDER BY id"
    ).fetchall()
    rows_b = connect(b).execute(
        "SELECT session_id, locale, path, event_type, sku, revenue_chf, referrer,"
        " device FROM events ORDER BY id"
    ).fetchall()
    assert [tuple(r) for r in rows_a] == [tuple(r) for r in rows_b]


def test_volume_is_in_the_expected_range(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
    assert 30_000 <= n <= 55_000


def test_finding_1_the_cheap_probe_outdraws_the_hero_product(conn):
    assert _views(conn, "/p/arv-p240") > _views(conn, "/p/arv-tx3")


def test_finding_1_but_the_hero_products_carry_the_revenue(conn):
    hero = _revenue(conn, "arv-tx3") + _revenue(conn, "arv-ab30")
    rest = sum(
        _revenue(conn, sku)
        for sku in ("arv-p240", "arv-s1", "clb-k2", "clb-vf1", "clb-cr12", "clb-r94")
    )
    assert hero > rest


def test_finding_2_de_ch_has_the_most_sessions(conn):
    rows = conn.execute(
        "SELECT locale, COUNT(DISTINCT session_id) AS s FROM events"
        " GROUP BY locale ORDER BY s DESC"
    ).fetchall()
    assert rows[0]["locale"] == "de-CH"


def test_finding_2_but_fr_ch_converts_far_worse(conn):
    def rate(locale):
        row = conn.execute(
            "SELECT COUNT(DISTINCT session_id) AS sessions,"
            " COUNT(DISTINCT CASE WHEN event_type='purchase' THEN session_id END) AS buyers"
            " FROM events WHERE locale=?", (locale,)
        ).fetchone()
        return row["buyers"] / row["sessions"]

    assert rate("fr-CH") < rate("de-CH") * 0.65


def test_finding_3_checkout_is_on_every_revenue_path(conn):
    buyers = conn.execute(
        "SELECT DISTINCT session_id FROM events WHERE event_type='purchase'"
    ).fetchall()
    checkout = conn.execute(
        "SELECT DISTINCT session_id FROM events WHERE event_type='begin_checkout'"
    ).fetchall()
    assert {r["session_id"] for r in buyers} <= {r["session_id"] for r in checkout}


def test_finding_4_the_guide_is_a_major_entry_point(conn):
    total = conn.execute(
        "SELECT COUNT(DISTINCT session_id) AS n FROM events"
    ).fetchone()["n"]
    guide = conn.execute(
        "SELECT COUNT(DISTINCT session_id) AS n FROM events"
        " WHERE path='/guide/avalanche-basics'"
    ).fetchone()["n"]
    assert 0.24 <= guide / total <= 0.36


def test_finding_5_legal_pages_are_almost_invisible(conn):
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE event_type='page_view'"
    ).fetchone()["n"]
    legal = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE event_type='page_view'"
        " AND path LIKE '/legal/%'"
    ).fetchone()["n"]
    assert 0 < legal / total < 0.01
