"""Generate the product placeholder SVGs.

Glyphs, ground gradients and fills come from the Claude Design comp
("Firn Shop.dc.html"), mapped onto our catalogue by product type. Everything
is drawn locally from path data — no third-party imagery enters the repo, so
there is no licensing question and nothing to fetch at runtime.

Products that have a photograph in app/static/img/photo/ use that instead; see
Product.has_photo in app/catalog.py. These glyphs still cover every SKU, so the
shop renders correctly whether or not the photos are present.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.catalog import PRODUCTS  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "img"

# sku -> (glyph path, ground start, ground end, glyph fill). The comp draws
# each product on its own cool-toned ground so the cards read as a set without
# being identical.
GLYPHS = {
    # Transceiver — handset with screen and buttons.
    "arv-tx3": (
        "M66 22h68a12 12 0 0 1 12 12v72a12 12 0 0 1-12 12H66a12 12 0 0 1-12-12V34"
        "a12 12 0 0 1 12-12Zm8 14v30h52V36H74Zm4 44h44v8H78v-8Zm0 18h28v8H78v-8Z",
        "#CBDDE2", "#8FB3BD", "#20404B",
    ),
    # Probe — collapsed shaft with depth markings.
    "arv-p240": (
        "M28 118 148 18l10 12L38 130l-10-12Zm34-26 10 12m14-36 10 12m14-36 10 12",
        "#D8E3E0", "#9CB6B0", "#22403C",
    ),
    # Shovel — blade and shaft.
    "arv-s1": (
        "M92 14h16v56h26l-34 52-34-52h26V14Zm-4 66 12 18 12-18H88Z",
        "#D5DEE4", "#93A7B6", "#233440",
    ),
    # Airbag pack — rounded pack body with lid and straps.
    "arv-ab30": (
        "M70 44a30 30 0 0 1 60 0v70a10 10 0 0 1-10 10H80a10 10 0 0 1-10-10V44Z"
        "m14 6v20h32V50H84Zm-2 40h36v8H82v-8Z",
        "#C9DAE0", "#87A9B4", "#1E3A44",
    ),
    # Helmet — domed shell with brim.
    "clb-k2": (
        "M38 104a62 62 0 0 1 124 0v8H38v-8Zm18-6h88a44 44 0 0 0-88 0Z",
        "#DCE4E1", "#9AB4AC", "#213E38",
    ),
    # Via ferrata set — two carabiners.
    "clb-vf1": (
        "M62 34a28 28 0 1 1 0 56 28 28 0 0 1 0-56Zm0 14a14 14 0 1 0 0 28 14 14 0 0 0 0-28Z"
        "m76 6a26 26 0 1 1 0 52 26 26 0 0 1 0-52Zm0 13a13 13 0 1 0 0 26 13 13 0 0 0 0-26Z",
        "#D3DFE5", "#92AAB8", "#22383F",
    ),
    # Crampons — frame with points.
    "clb-cr12": (
        "M46 52h108v18l-12 34-14-26-14 26-14-26-14 26-14-26-12-34V52Z",
        "#CFDBE1", "#8EA9B5", "#1F3944",
    ),
    # Rope — coiled loops.
    "clb-r94": (
        "M100 24a46 46 0 1 1 0 92 46 46 0 0 1 0-92Zm0 16a30 30 0 1 0 0 60 30 30 0 0 0 0-60Z"
        "m0 14a16 16 0 1 1 0 32 16 16 0 0 1 0-32Z",
        "#D7E1DF", "#96B0AB", "#1F3C38",
    ),
}

# Source paths are drawn in a 200x140 box but are not all centred or the same
# visual weight, so each is fitted: scaled to TARGET of the box and centred on
# its own bounding box. BBOXES are measured from the path data below.
TARGET = 0.72

# sku -> (min-x, min-y, max-x, max-y), measured from the rendered paths with
# getBBox() rather than estimated; see fit() for how they become a transform.
BBOXES = {
    "arv-tx3": (54, 22, 146, 118),
    "arv-p240": (28, 18, 158, 130),
    "arv-s1": (66, 14, 134, 122),
    "arv-ab30": (70, 14, 130, 124),
    "clb-k2": (38, 42, 162, 112),
    "clb-vf1": (34, 34, 164, 106),
    "clb-cr12": (46, 44, 154, 104),
    "clb-r94": (54, 24, 146, 116),
}


def fit(sku: str) -> str:
    """Scale a glyph to TARGET of the 200x140 box and centre it."""
    x0, y0, x1, y1 = BBOXES[sku]
    w, h = x1 - x0, y1 - y0
    scale = min(200 * TARGET / w, 140 * TARGET / h)
    cx, cy = x0 + w / 2, y0 + h / 2
    return (
        f"translate({100 - cx * scale:.2f} {70 - cy * scale:.2f}) scale({scale:.4f})"
    )


TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 140" width="400" \
height="280" role="img" aria-label="{sku}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0.62" y2="1">
      <stop offset="0" stop-color="{c1}"/>
      <stop offset="1" stop-color="{c2}"/>
    </linearGradient>
    <radialGradient id="s" cx="0.26" cy="0.18" r="0.62">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="140" fill="url(#g)"/>
  <rect width="200" height="140" fill="url(#s)"/>
  <path d="{path}" fill="{glyph}" fill-rule="evenodd"
        stroke="{glyph}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"
        transform="{transform}"/>
</svg>
"""


def generate() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for sku in sorted(PRODUCTS):
        path, c1, c2, glyph = GLYPHS[sku]
        # The probe is an open stroked path; the rest are closed fills that need
        # only a hairline to keep thin details from disappearing when scaled.
        stroke = 4 if sku == "arv-p240" else 0
        (OUT / f"{sku}.svg").write_text(
            TEMPLATE.format(
                sku=sku, path=path, c1=c1, c2=c2, glyph=glyph,
                stroke=stroke, transform=fit(sku),
            ),
            encoding="utf-8",
        )
    return len(PRODUCTS)


if __name__ == "__main__":
    print(f"Wrote {generate()} placeholder SVGs to {OUT}")
