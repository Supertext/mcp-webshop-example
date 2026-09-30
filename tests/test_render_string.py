import json

import pytest

from app.i18n import Catalogs, render_notice, render_string, short_hash, state_counts


@pytest.fixture
def catalogs(tmp_path):
    source = tmp_path / "source.en.json"
    source.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "cart.add": {
                "text": "Add to cart", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            },
            "risky": {
                "text": "Tom & Jerry <b>", "class": "marketing",
                "surfaces": ["*"], "translatable": True,
            },
            "safety": {
                "text": "Check the transceiver.", "class": "safety_critical",
                "surfaces": ["*"], "translatable": True, "policy": "human_only",
            },
            "notice.withheld.title": {
                "text": "Available in English only", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            },
            "never.translated": {
                "text": "Retire after any fall factor 2 event.", "class": "legal",
                "surfaces": ["*"], "translatable": True, "policy": "human_only",
            },
            "notice.withheld.body": {
                "text": "This section requires professional verification before it can"
                        " be published in this language.",
                "class": "ui_chrome", "surfaces": ["*"], "translatable": True,
            },
        },
    }))
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "fr-CH.json").write_text(json.dumps({
        "schema_version": 1, "locale": "fr-CH",
        "strings": {
            "cart.add": {
                "text": "Ajouter au panier", "state": "machine",
                "source_hash": short_hash("Add to cart"),
                "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
            },
            "safety": {
                "text": "Contrôlez le DVA.", "state": "machine",
                "source_hash": short_hash("Check the transceiver."),
                "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
            },
        },
    }))
    c = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    c.refresh()
    return c


def test_plain_mode_emits_a_wrapper_with_state(catalogs):
    html = str(render_string(catalogs, "cart.add", "fr-CH", trust=False))
    assert 'data-state="machine"' in html
    assert "Ajouter au panier" in html
    assert "trust" not in html


def test_trust_mode_adds_the_marker_glyph(catalogs):
    html = str(render_string(catalogs, "cart.add", "fr-CH", trust=True))
    assert 'class="s trust"' in html
    assert "MT" in html


def test_text_is_html_escaped(catalogs):
    html = str(render_string(catalogs, "risky", "fr-CH", trust=False))
    assert "&amp;" in html
    assert "<b>" not in html


def test_state_counts_tallies_resolved_states(catalogs):
    counts = state_counts(catalogs, ["cart.add", "risky", "safety"], "fr-CH")
    assert counts == {"machine": 1, "fallback": 1, "withheld": 1}


def test_human_only_with_no_translation_at_all_is_fallback_not_withheld(catalogs):
    """A human_only string that was never translated is `fallback`, not `withheld`:
    nothing is being suppressed, so the notice must not claim a review is under way."""
    assert catalogs.resolve("never.translated", "fr-CH").state == "fallback"
    assert str(render_notice(catalogs, "never.translated", "fr-CH")) == ""


def test_withheld_string_gets_the_english_only_notice(catalogs):
    html = str(render_notice(catalogs, "safety", "fr-CH"))
    assert "Available in English only" in html
    assert "withheld-notice" in html


def test_non_withheld_strings_get_no_notice(catalogs):
    assert str(render_notice(catalogs, "cart.add", "fr-CH")) == ""
    assert str(render_notice(catalogs, "cart.add", "en")) == ""


@pytest.fixture
def catalogs_with_risky_notice(tmp_path):
    """Fixture with unsafe characters in notice strings to test escaping."""
    source = tmp_path / "source.en.json"
    source.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "safety": {
                "text": "Check the transceiver.", "class": "safety_critical",
                "surfaces": ["*"], "translatable": True, "policy": "human_only",
            },
            "notice.withheld.title": {
                "text": "Tom & Jerry <b>", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            },
            "notice.withheld.body": {
                "text": "Risk & reward <script>", "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            },
        },
    }))
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "fr-CH.json").write_text(json.dumps({
        "schema_version": 1, "locale": "fr-CH",
        "strings": {
            "safety": {
                "text": "Contrôlez le DVA.", "state": "machine",
                "source_hash": short_hash("Check the transceiver."),
                "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
            },
        },
    }))
    c = Catalogs(source_path=source, locales_dir=locales, locales=("fr-CH",))
    c.refresh()
    return c


def test_notice_text_is_html_escaped(catalogs_with_risky_notice):
    """Verify that notice title and body escape HTML to prevent injection."""
    html = str(render_notice(catalogs_with_risky_notice, "safety", "fr-CH"))
    # Verify ampersands and tags are escaped
    assert "&amp;" in html
    assert "&lt;b&gt;" in html
    assert "&lt;script&gt;" in html
    # Verify the markup structure is intact
    assert "withheld-notice" in html
    # Verify unescaped tags from test content are not present (raw tags would be injection)
    assert "Tom & Jerry <b>" not in html
    assert "Risk & reward <script>" not in html
