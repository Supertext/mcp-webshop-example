import json

from app.i18n import TARGET_LOCALES
from scripts.reset_demo import reset_ledger, reset_locales


def test_reset_locales_empties_every_catalogue(tmp_path):
    for locale in TARGET_LOCALES:
        (tmp_path / f"{locale}.json").write_text(json.dumps({
            "schema_version": 1, "locale": locale,
            "strings": {"x": {"text": "y", "state": "verified"}},
        }))

    reset_locales(tmp_path)

    for locale in TARGET_LOCALES:
        data = json.loads((tmp_path / f"{locale}.json").read_text())
        assert data == {"schema_version": 1, "locale": locale, "strings": {}}


def test_reset_ledger_clears_orders_but_keeps_the_budget(tmp_path):
    path = tmp_path / "verification_ledger.json"
    path.write_text(json.dumps({
        "budget": {"amount": 100.0, "currency": "CHF"},
        "orders": [{"txn_id": "TX-1", "status": "completed"}],
    }))

    reset_ledger(path)

    data = json.loads(path.read_text())
    assert data["orders"] == []
    assert data["budget"] == {"amount": 100.0, "currency": "CHF"}
