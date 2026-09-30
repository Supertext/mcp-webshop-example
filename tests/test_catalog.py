import pytest

from app.catalog import CATEGORIES, PRODUCTS, in_category
from app.i18n import SOURCE_PATH, load_source

REQUIRED_SUFFIXES = ("name", "tagline", "short", "long", "safety_instructions", "care")


def test_eight_products_split_across_two_categories():
    assert len(PRODUCTS) == 8
    assert set(CATEGORIES) == {"avalanche-safety", "climbing"}
    assert len(in_category("avalanche-safety")) == 4
    assert len(in_category("climbing")) == 4


def test_every_product_has_all_its_content_keys():
    source = load_source(SOURCE_PATH)
    for sku in PRODUCTS:
        for suffix in REQUIRED_SUFFIXES:
            key = f"product.{sku}.{suffix}"
            assert key in source["strings"], f"missing {key}"


def test_certification_strings_are_not_translatable():
    source = load_source(SOURCE_PATH)
    for _sku, product in PRODUCTS.items():
        if product.cert_key is None:
            continue
        entry = source["strings"][product.cert_key]
        assert entry["translatable"] is False
        assert entry["class"] == "certification"


def test_safety_instructions_are_classed_safety_critical():
    """The *class* is shipped; the `policy` is not.

    Deciding which strings need `policy: human_only` is the workshop's live
    exercise, so source.en.json ships without it and the agent argues for it on
    stage. What must always hold is that the taxonomy is honest: every safety
    instruction is classed safety_critical, so the agent has something factual
    to reason from. Enforcement of the policy itself is covered in
    tests/test_resolve.py.
    """
    source = load_source(SOURCE_PATH)
    for sku in PRODUCTS:
        entry = source["strings"][f"product.{sku}.safety_instructions"]
        assert entry["class"] == "safety_critical"


def test_content_inventory_is_close_to_target():
    source = load_source(SOURCE_PATH)
    assert 170 <= len(source["strings"]) <= 210


def test_spec_labels_are_shared_not_duplicated_per_product():
    """Every product's spec rows label themselves from the shared label.spec.* keys,
    so "Weight" is authored and translated once rather than eight times."""
    source = load_source(SOURCE_PATH)
    for product in PRODUCTS.values():
        for name in product.spec_names:
            assert f"label.spec.{name}" in source["strings"]
            assert f"product.{product.sku}.spec.{name}" in source["strings"]
        assert not any(
            k.startswith(f"product.{product.sku}.spec.") and k.endswith(".label")
            for k in source["strings"]
        ), "per-product spec labels should be shared label.spec.* keys instead"


def test_every_content_class_is_represented():
    source = load_source(SOURCE_PATH)
    used = {entry["class"] for entry in source["strings"].values()}
    assert used == {
        "ui_chrome", "marketing", "product_prose", "product_spec",
        "safety_critical", "legal", "certification", "transactional",
    }


@pytest.mark.parametrize("slug", ["terms", "returns", "warranty", "privacy", "shipping"])
def test_each_legal_page_has_a_legal_class_body(slug):
    source = load_source(SOURCE_PATH)
    entry = source["strings"][f"legal.{slug}.body"]
    assert entry["class"] == "legal"
