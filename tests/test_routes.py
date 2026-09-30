import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_home_renders_in_english():
    response = client.get("/")
    assert response.status_code == 200
    assert "Firn" in response.text


@pytest.mark.parametrize("locale", ["de-CH", "fr-CH", "it-CH"])
def test_home_renders_in_every_target_locale(locale):
    assert client.get(f"/{locale}/").status_code == 200


def test_unknown_locale_prefix_is_not_stripped():
    assert client.get("/zz-ZZ/").status_code == 404


@pytest.mark.parametrize("sku", [
    "arv-tx3", "arv-p240", "arv-s1", "arv-ab30",
    "clb-k2", "clb-vf1", "clb-cr12", "clb-r94",
])
def test_every_product_page_renders(sku):
    assert client.get(f"/p/{sku}").status_code == 200


def test_unknown_product_is_404():
    assert client.get("/p/nope").status_code == 404


@pytest.mark.parametrize("category", ["avalanche-safety", "climbing"])
def test_category_pages_render(category):
    assert client.get(f"/c/{category}").status_code == 200


@pytest.mark.parametrize("slug", ["terms", "returns", "warranty", "privacy", "shipping"])
def test_legal_pages_render(slug):
    assert client.get(f"/legal/{slug}").status_code == 200


def test_guide_renders():
    assert client.get("/guide/avalanche-basics").status_code == 200


def test_strings_are_wrapped_with_their_state():
    response = client.get("/p/arv-tx3")
    assert response.text.count('data-state=') >= 20


def test_trust_query_param_enables_the_overlay():
    with_trust = client.get("/p/arv-tx3?trust=1")
    without = client.get("/p/arv-tx3")
    assert 'class="s trust"' in with_trust.text
    assert 'class="s trust"' not in without.text


def test_certification_code_is_never_translated():
    response = client.get("/fr-CH/p/arv-tx3")
    assert "EN 300 718-1" in response.text
    assert 'data-state="source_locked"' in response.text


def test_no_withheld_notice_before_anything_is_translated():
    """At cold start nothing has been translated, so legal pages fall back to English
    with no notice — claiming a review is under way would be false."""
    response = client.get("/fr-CH/legal/shipping")
    assert "withheld-notice" not in response.text


def test_human_only_string_is_withheld_when_unverified(tmp_path, monkeypatch):
    """A human_only string with a machine entry renders English, tinted withheld.

    Isolated from whatever is in locales/ — after `make translate` the real
    catalogues are full, and this test must hold either way.
    """
    _withhold(tmp_path, monkeypatch, "product.arv-tx3.safety_instructions")

    response = client.get("/fr-CH/p/arv-tx3?trust=1")
    assert 'data-state="withheld"' in response.text
    assert "Texte machine" not in response.text  # machine text never published


def _withhold(tmp_path, monkeypatch, key):
    """Point the app at catalogues where `key` is human_only with an unverified
    fr-CH machine entry, so it resolves `withheld`. Returns its English text."""
    import json

    import app.main as main
    from app import i18n

    src = json.loads(i18n.SOURCE_PATH.read_text(encoding="utf-8"))
    src["strings"][key] = {**src["strings"][key], "policy": "human_only"}
    english = src["strings"][key]["text"]
    (tmp_path / "source.en.json").write_text(json.dumps(src), encoding="utf-8")
    (tmp_path / "fr-CH.json").write_text(json.dumps({
        "schema_version": 1, "locale": "fr-CH", "strings": {key: {
            "text": "Texte machine", "state": "machine",
            "source_hash": i18n.short_hash(english),
            "engine": "supertext-api", "updated_at": "2026-09-01T00:00:00Z"}}}), encoding="utf-8")
    monkeypatch.setattr(i18n, "CATALOGS", i18n.Catalogs(
        source_path=tmp_path / "source.en.json", locales_dir=tmp_path))
    monkeypatch.setattr(main, "CATALOGS", i18n.CATALOGS)
    return english


@pytest.mark.parametrize("key, path", [
    ("product.arv-ab30.safety_instructions", "/fr-CH/p/arv-ab30"),
    ("product.arv-ab30.care", "/fr-CH/p/arv-ab30"),
    ("product.arv-ab30.short", "/fr-CH/p/arv-ab30"),
    ("product.arv-ab30.long", "/fr-CH/p/arv-ab30"),
    ("guide.standfirst", "/fr-CH/guide/avalanche-basics"),
    ("guide.body3", "/fr-CH/guide/avalanche-basics"),
    ("guide.pullquote", "/fr-CH/guide/avalanche-basics"),
    ("home.prop2.body", "/fr-CH/"),
    ("home.guide.body", "/fr-CH/"),
    ("category.avalanche-safety.intro", "/fr-CH/c/avalanche-safety"),
    ("legal.shipping.body", "/fr-CH/legal/shipping"),
])
def test_every_withheld_block_carries_the_notice(tmp_path, monkeypatch, key, path):
    """Spec 5.3: any withheld block shows English *with* the notice beside it —
    whichever strings the policy lands on, not just the safety section."""
    from markupsafe import escape

    english = _withhold(tmp_path, monkeypatch, key)

    html = client.get(path).text
    assert html.count("withheld-notice") == 1
    after_notice = html.split("withheld-notice", 1)[1]
    assert str(escape(english))[:40] in after_notice[:800]
