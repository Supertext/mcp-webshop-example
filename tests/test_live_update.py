import json

from fastapi.testclient import TestClient

from app.i18n import CATALOGS, LOCALES_DIR, short_hash
from app.main import app, keys_for_path

client = TestClient(app)


def test_state_endpoint_returns_a_catalog_version():
    response = client.get("/_state?path=/p/arv-tx3&locale=fr-CH")
    assert response.status_code == 204
    assert response.headers["X-Catalog-Version"]


def test_catalog_version_changes_when_a_locale_file_changes():
    path = LOCALES_DIR / "fr-CH.json"
    original = path.read_text(encoding="utf-8")
    before = client.get("/_state?path=/&locale=fr-CH").headers["X-Catalog-Version"]
    try:
        path.write_text(json.dumps({
            "schema_version": 1, "locale": "fr-CH",
            "strings": {
                "nav.cart": {
                    "text": "Panier", "state": "machine",
                    "source_hash": short_hash(CATALOGS.source["strings"]["nav.cart"]["text"]),
                    "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
                }
            },
        }), encoding="utf-8")
        after = client.get("/_state?path=/&locale=fr-CH").headers["X-Catalog-Version"]
        assert after != before
    finally:
        path.write_text(original, encoding="utf-8")
        CATALOGS.refresh()


def test_state_counts_header_is_valid_json():
    counts = json.loads(client.get("/_state?path=/&locale=en").headers["X-State-Counts"])
    assert isinstance(counts, dict)
    assert sum(counts.values()) > 0


def test_keys_for_path_matches_global_and_specific_surfaces():
    keys = keys_for_path("/p/arv-tx3")
    assert "nav.cart" in keys
    assert "product.arv-tx3.safety_instructions" in keys
    assert "product.clb-k2.safety_instructions" not in keys


def test_trust_legend_only_appears_in_trust_mode():
    assert 'id="trust-legend"' not in client.get("/").text
    assert 'id="trust-legend"' in client.get("/?trust=1").text