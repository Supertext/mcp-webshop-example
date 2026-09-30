"""scripts/translate.py — everything except the network.

The API is stubbed at httpx.Client.post so these run offline and cost
nothing. What they pin: which strings get sent, how batches are cut, what
gets written, and that a human's work is never overwritten.
"""

from __future__ import annotations

import json

import pytest

from app.i18n import short_hash
from scripts import translate as t

SRC = {
    "nav.cart": {"text": "Cart", "translatable": True},
    "product.x.cert": {"text": "EN 12492", "translatable": False},
    "legal.body": {"text": "Long legal text. " * 10, "translatable": True},
    "safety": {"text": "Check the cartridge.", "translatable": True},
}


def test_untranslatable_strings_are_never_sent():
    keys = t.pending_keys(SRC, {"strings": {}}, force=False)
    assert "product.x.cert" not in keys
    assert set(keys) == {"nav.cart", "legal.body", "safety"}


@pytest.mark.parametrize("state", ["pending", "verified"])
def test_human_states_are_never_overwritten(state):
    catalog = {"strings": {"safety": {"text": "…", "state": state, "source_hash": "00000000"}}}
    assert "safety" not in t.pending_keys(SRC, catalog, force=True)


def test_fresh_machine_entry_is_skipped_unless_forced():
    fresh = {"text": "Panier", "state": "machine", "source_hash": short_hash("Cart")}
    catalog = {"strings": {"nav.cart": fresh}}
    assert "nav.cart" not in t.pending_keys(SRC, catalog, force=False)
    assert "nav.cart" in t.pending_keys(SRC, catalog, force=True)


def test_stale_machine_entry_is_refreshed():
    stale = {"text": "Panier", "state": "machine", "source_hash": "deadbeef"}
    assert "nav.cart" in t.pending_keys(SRC, {"strings": {"nav.cart": stale}}, force=False)


def test_batches_respect_the_character_ceiling(monkeypatch):
    monkeypatch.setattr(t, "BATCH_CHARS", 200)
    keys = ["nav.cart", "legal.body", "safety"]
    groups = t.batches(SRC, keys)
    assert [k for g in groups for k in g] == keys  # order preserved
    for g in groups:
        assert sum(len(SRC[k]["text"]) for k in g) <= 200 or len(g) == 1


def test_translate_writes_machine_entries_with_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "LOCALES_DIR", tmp_path)
    monkeypatch.setenv("SUPERTEXT_API_KEY", "test-key")
    sent: list[dict] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    def fake_post(self, url, headers=None, json=None, timeout=None):
        sent.append({"url": url, "auth": headers["Authorization"], "body": json})
        return FakeResponse({"translated_text": [f"FR:{s}" for s in json["text"]]})

    monkeypatch.setattr(t.httpx.Client, "post", fake_post)
    monkeypatch.setattr(t.time, "sleep", lambda _: None)

    t.translate(SRC, ["fr-CH"], force=False)

    written = json.loads((tmp_path / "fr-CH.json").read_text(encoding="utf-8"))
    assert written["locale"] == "fr-CH"
    assert set(written["strings"]) == {"nav.cart", "legal.body", "safety"}
    entry = written["strings"]["nav.cart"]
    assert entry == {
        "text": "FR:Cart",
        "state": "machine",
        "source_hash": short_hash("Cart"),
        "engine": "supertext-api",
        "updated_at": entry["updated_at"],
    }
    assert entry["updated_at"].endswith("Z")
    assert sent[0]["url"].endswith("/translate/ai/text")
    assert sent[0]["auth"] == "Supertext-Auth-Key test-key"
    assert sent[0]["body"]["target_lang"] == "fr-CH"
    assert "EN 12492" not in [s for r in sent for s in r["body"]["text"]]


def test_segment_count_mismatch_aborts(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "LOCALES_DIR", tmp_path)
    monkeypatch.setenv("SUPERTEXT_API_KEY", "test-key")

    class Short:
        status_code = 200

        def json(self):
            return {"translated_text": ["only one"]}

    monkeypatch.setattr(t.httpx.Client, "post", lambda *a, **k: Short())
    monkeypatch.setattr(t.time, "sleep", lambda _: None)
    with pytest.raises(SystemExit, match="sent 3 segments, got 1"):
        t.translate(SRC, ["fr-CH"], force=False)
    assert not (tmp_path / "fr-CH.json").exists()


def test_missing_key_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERTEXT_API_KEY", raising=False)
    monkeypatch.setattr(t, "ROOT", tmp_path)  # no .env there
    with pytest.raises(SystemExit, match="SUPERTEXT_API_KEY is not set"):
        t.api_key()
