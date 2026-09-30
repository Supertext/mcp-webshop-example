import json

import pytest

from app.i18n import SOURCE_PATH, load_source, short_hash


def test_short_hash_is_eight_lowercase_hex_chars():
    result = short_hash("Add to cart")
    assert len(result) == 8
    assert result == result.lower()
    assert all(c in "0123456789abcdef" for c in result)


def test_short_hash_is_stable_and_distinct():
    assert short_hash("Add to cart") == short_hash("Add to cart")
    assert short_hash("Add to cart") != short_hash("Add to basket")


def test_load_source_accepts_the_real_content_file():
    source = load_source(SOURCE_PATH)
    assert source["default_locale"] == "en"
    assert len(source["strings"]) > 0


def test_load_source_rejects_unknown_content_class(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "a.b": {"text": "x", "class": "nonsense", "surfaces": ["*"], "translatable": True}
        },
    }))
    with pytest.raises(ValueError, match="unknown class 'nonsense'"):
        load_source(bad)


def test_load_source_rejects_missing_required_field(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {"a.b": {"text": "x", "class": "ui_chrome"}},
    }))
    with pytest.raises(ValueError, match="missing required field"):
        load_source(bad)


def test_load_source_rejects_unknown_policy(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": 1,
        "default_locale": "en",
        "strings": {
            "a.b": {
                "text": "x", "class": "legal", "surfaces": ["*"],
                "translatable": True, "policy": "maybe",
            }
        },
    }))
    with pytest.raises(ValueError, match="unknown policy 'maybe'"):
        load_source(bad)
