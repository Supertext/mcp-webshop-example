import json

import pytest

from app.i18n import Catalogs, short_hash


@pytest.fixture
def paths(tmp_path):
    source = tmp_path / "source.en.json"
    source.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "cart.add": {
                "text": "Add to cart", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            }
        },
    }))
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "fr-CH.json").write_text(
        json.dumps({"schema_version": 1, "locale": "fr-CH", "strings": {}})
    )
    return source, locales


def test_picks_up_a_translation_written_after_load(paths):
    source, locales = paths
    catalogs = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    catalogs.refresh()
    assert catalogs.resolve("cart.add", "fr-CH").state == "fallback"

    (locales / "fr-CH.json").write_text(json.dumps({
        "schema_version": 1, "locale": "fr-CH",
        "strings": {
            "cart.add": {
                "text": "Ajouter au panier", "state": "machine",
                "source_hash": short_hash("Add to cart"),
                "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
            }
        },
    }))

    catalogs.refresh()
    result = catalogs.resolve("cart.add", "fr-CH")
    assert result.text == "Ajouter au panier"
    assert result.state == "machine"


def test_version_changes_when_a_file_changes(paths):
    source, locales = paths
    catalogs = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    catalogs.refresh()
    before = catalogs.version

    (locales / "fr-CH.json").write_text(
        json.dumps({"schema_version": 1, "locale": "fr-CH", "strings": {"x": 1}})
    )
    catalogs.refresh()

    assert catalogs.version != before


def test_version_is_stable_when_nothing_changes(paths):
    source, locales = paths
    catalogs = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    catalogs.refresh()
    before_version = catalogs.version
    before_source = catalogs.source
    before_locale = catalogs.locales["fr-CH"]

    catalogs.refresh()

    # Version must be unchanged
    assert catalogs.version == before_version
    # Objects must not be re-read (same identity, not just equal)
    assert catalogs.source is before_source
    assert catalogs.locales["fr-CH"] is before_locale


def test_picks_up_a_source_file_change(paths):
    source, locales = paths
    catalogs = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    catalogs.refresh()
    before_version = catalogs.version
    assert catalogs.source["strings"]["cart.add"]["text"] == "Add to cart"

    # Modify the source file
    source.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "cart.add": {
                "text": "Add to shopping cart", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            }
        },
    }))

    catalogs.refresh()

    # Version must change
    assert catalogs.version != before_version
    # New source text must be visible
    assert catalogs.source["strings"]["cart.add"]["text"] == "Add to shopping cart"
