from __future__ import annotations

import dataclasses
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRODUCTS_PATH = ROOT / "content" / "products.json"
PHOTO_DIR = ROOT / "app" / "static" / "img" / "photo"

CATEGORIES = ("avalanche-safety", "climbing")


@dataclasses.dataclass(frozen=True)
class Product:
    sku: str
    price_chf: int
    category: str
    cert_key: str | None
    spec_names: tuple[str, ...]
    image: str

    @property
    def name_key(self) -> str:
        return f"product.{self.sku}.name"

    @property
    def has_photo(self) -> bool:
        """True when a product photograph exists for this SKU.

        Only some products have one; the rest fall back to the generated glyph
        SVG. Checked against the filesystem so the templates stay correct if
        photos are added or removed without a code change.
        """
        return (PHOTO_DIR / f"{self.sku}-1200.jpg").is_file()

    @property
    def spec_keys(self) -> tuple[str, ...]:
        return tuple(f"product.{self.sku}.spec.{n}" for n in self.spec_names)


def load_products(path: pathlib.Path = PRODUCTS_PATH) -> dict[str, Product]:
    data = json.loads(path.read_text(encoding="utf-8"))
    products: dict[str, Product] = {}
    for row in data["products"]:
        sku = row["sku"]
        products[sku] = Product(
            sku=sku,
            price_chf=row["price_chf"],
            category=row["category"],
            cert_key=f"product.{sku}.cert" if row["cert"] else None,
            spec_names=tuple(row["specs"]),
            image=row["image"],
        )
    return products


PRODUCTS = load_products()


def in_category(category: str) -> list[Product]:
    return [p for p in PRODUCTS.values() if p.category == category]
