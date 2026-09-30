import json

import pytest

from app.ledger import add_order, close_order, load_ledger, spend_summary


@pytest.fixture
def ledger_path(tmp_path):
    path = tmp_path / "verification_ledger.json"
    path.write_text(json.dumps({
        "budget": {"amount": 100.00, "currency": "CHF"},
        "orders": [],
    }))
    return path


def test_add_order_records_it_as_in_progress(ledger_path):
    add_order("TX-1", "legal.shipping.body", "fr-CH", 412, 61.80, "CHF",
              "2026-08-31T09:31:05Z", path=ledger_path)
    orders = load_ledger(ledger_path)["orders"]
    assert len(orders) == 1
    assert orders[0]["txn_id"] == "TX-1"
    assert orders[0]["status"] == "in_progress"
    assert orders[0]["completed_at"] is None
    assert orders[0]["cost"] == {"amount": 61.80, "currency": "CHF"}


def test_close_order_marks_it_completed(ledger_path):
    add_order("TX-1", "k", "fr-CH", 10, 1.50, "CHF", "2026-08-31T09:31:05Z", path=ledger_path)
    close_order("TX-1", "2026-08-31T09:48:12Z", path=ledger_path)
    order = load_ledger(ledger_path)["orders"][0]
    assert order["status"] == "completed"
    assert order["completed_at"] == "2026-08-31T09:48:12Z"


def test_close_unknown_order_raises(ledger_path):
    with pytest.raises(KeyError, match="TX-NOPE"):
        close_order("TX-NOPE", "2026-08-31T09:48:12Z", path=ledger_path)


def test_adding_a_duplicate_txn_id_raises(ledger_path):
    add_order("TX-1", "k", "fr-CH", 10, 1.50, "CHF", "2026-08-31T09:31:05Z", path=ledger_path)
    with pytest.raises(ValueError, match="TX-1"):
        add_order("TX-1", "k2", "fr-CH", 10, 1.50, "CHF", "2026-08-31T09:32:00Z",
                  path=ledger_path)


def test_spend_summary_totals_per_currency_without_converting(ledger_path):
    add_order("TX-1", "k1", "fr-CH", 10, 12.40, "CHF", "2026-08-31T09:31:05Z", path=ledger_path)
    add_order("TX-2", "k2", "de-CH", 20, 7.60, "CHF", "2026-08-31T09:33:00Z", path=ledger_path)
    close_order("TX-1", "2026-08-31T09:48:12Z", path=ledger_path)

    summary = spend_summary(ledger_path)
    assert summary["budget"] == {"amount": 100.00, "currency": "CHF"}
    assert summary["committed"] == {"CHF": 20.00}
    assert summary["open"] == 1
    assert summary["closed"] == 1


def test_atomic_write_leaves_no_tmp_file(ledger_path):
    add_order("TX-1", "k", "fr-CH", 10, 5.00, "CHF", "2026-08-31T09:31:05Z", path=ledger_path)
    close_order("TX-1", "2026-08-31T09:48:12Z", path=ledger_path)

    # Verify ledger file parses as valid JSON
    data = load_ledger(ledger_path)
    assert data["orders"][0]["status"] == "completed"

    # Verify no .tmp file is left behind
    tmp_path = ledger_path.with_name(ledger_path.name + ".tmp")
    assert not tmp_path.exists()
