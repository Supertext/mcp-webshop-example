import pytest

from app.analytics import connect, init_db, locale_funnel, record, top_paths


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.sqlite")
    init_db(c)
    return c


def test_recording_and_counting_page_views(conn):
    for _ in range(3):
        record(conn, ts="2026-08-01T10:00:00Z", session_id="s1", locale="de-CH",
               path="/p/arv-tx3", event_type="page_view")
    record(conn, ts="2026-08-01T10:01:00Z", session_id="s2", locale="fr-CH",
           path="/", event_type="page_view")

    rows = {r["path"]: r["views"] for r in top_paths(conn)}
    assert rows["/p/arv-tx3"] == 3
    assert rows["/"] == 1


def test_purchase_carries_revenue(conn):
    record(conn, ts="2026-08-01T10:00:00Z", session_id="s1", locale="de-CH",
           path="/checkout", event_type="purchase", sku="arv-tx3", revenue_chf=449.0)
    row = conn.execute("SELECT SUM(revenue_chf) AS total FROM events").fetchone()
    assert row["total"] == 449.0


def test_unknown_event_type_is_rejected(conn):
    with pytest.raises(ValueError, match="unknown event_type"):
        record(conn, ts="2026-08-01T10:00:00Z", session_id="s1", locale="de-CH",
               path="/", event_type="teleport")


def test_locale_funnel_counts_each_stage(conn):
    record(conn, ts="t", session_id="s1", locale="fr-CH", path="/", event_type="page_view")
    record(conn, ts="t", session_id="s1", locale="fr-CH", path="/p/x",
           event_type="add_to_cart", sku="arv-s1")
    record(conn, ts="t", session_id="s1", locale="fr-CH", path="/checkout",
           event_type="begin_checkout")
    record(conn, ts="t", session_id="s2", locale="fr-CH", path="/", event_type="page_view")

    row = {r["locale"]: r for r in locale_funnel(conn)}["fr-CH"]
    assert row["sessions"] == 2
    assert row["carts"] == 1
    assert row["checkouts"] == 1
    assert row["purchases"] == 0