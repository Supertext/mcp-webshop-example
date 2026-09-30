import pytest

from app.i18n import Resolved, resolve, short_hash

SRC_TEXT = "Add to cart"
SAFETY_TEXT = "Perform a group transceiver check."


@pytest.fixture
def source():
    return {
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "cart.add": {
                "text": SRC_TEXT, "class": "ui_chrome",
                "surfaces": ["*"], "translatable": True,
            },
            "cert": {
                "text": "EN 300718-1", "class": "certification",
                "surfaces": ["*"], "translatable": False,
            },
            "safety": {
                "text": SAFETY_TEXT, "class": "safety_critical",
                "surfaces": ["*"], "translatable": True, "policy": "human_only",
            },
        },
    }


def _entry(text, state, source_text, **extra):
    return {
        "text": text, "state": state,
        "source_hash": short_hash(source_text),
        "engine": "supertext-api", "updated_at": "2026-08-31T09:00:00Z",
        **extra,
    }


def test_default_locale_returns_source(source):
    assert resolve(source, {}, "cart.add", "en") == Resolved(SRC_TEXT, "source")


def test_untranslatable_key_is_source_locked(source):
    catalogs = {"fr-CH": {"strings": {"cert": _entry("XX", "verified", "EN 300718-1")}}}
    assert resolve(source, catalogs, "cert", "fr-CH") == Resolved("EN 300718-1", "source_locked")


def test_missing_entry_falls_back_to_english(source):
    catalogs = {"fr-CH": {"strings": {}}}
    assert resolve(source, catalogs, "cart.add", "fr-CH") == Resolved(SRC_TEXT, "fallback")


def test_missing_locale_falls_back_to_english(source):
    assert resolve(source, {}, "cart.add", "fr-CH") == Resolved(SRC_TEXT, "fallback")


@pytest.mark.parametrize("state", ["machine", "pending", "verified"])
def test_fresh_entry_returns_its_stored_state(source, state):
    catalogs = {"fr-CH": {"strings": {"cart.add": _entry("Ajouter", state, SRC_TEXT)}}}
    assert resolve(source, catalogs, "cart.add", "fr-CH") == Resolved("Ajouter", state)


def test_edited_source_makes_translation_stale(source):
    catalogs = {"fr-CH": {"strings": {"cart.add": _entry("Ajouter", "verified", "OLD TEXT")}}}
    assert resolve(source, catalogs, "cart.add", "fr-CH") == Resolved("Ajouter", "stale")


@pytest.mark.parametrize("state", ["machine", "pending"])
def test_human_only_unverified_is_withheld(source, state):
    catalogs = {"fr-CH": {"strings": {"safety": _entry("Effectuez", state, SAFETY_TEXT)}}}
    assert resolve(source, catalogs, "safety", "fr-CH") == Resolved(SAFETY_TEXT, "withheld")


def test_human_only_verified_and_fresh_is_shown(source):
    catalogs = {"fr-CH": {"strings": {"safety": _entry("Effectuez", "verified", SAFETY_TEXT)}}}
    assert resolve(source, catalogs, "safety", "fr-CH") == Resolved("Effectuez", "verified")


def test_human_only_verified_but_stale_is_withheld_not_stale(source):
    """Ordering guarantee: the human_only check precedes the staleness check, so a
    legal string whose English changed after verification falls back to English
    rather than displaying a stale translation with a warning tint."""
    catalogs = {"fr-CH": {"strings": {"safety": _entry("Effectuez", "verified", "OLD")}}}
    assert resolve(source, catalogs, "safety", "fr-CH") == Resolved(SAFETY_TEXT, "withheld")


def test_unknown_key_raises(source):
    with pytest.raises(KeyError):
        resolve(source, {}, "no.such.key", "fr-CH")
