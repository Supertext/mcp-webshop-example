"""Download the self-hosted webfonts and regenerate app/static/css/fonts.css.

The demo must not depend on a CDN at runtime — conference wifi fails, and a
missing display face changes the whole page. The .woff2 files are committed
(they are SIL OFL licensed, ~420 KB total) so a fork works offline with no
setup step — run this only to refresh or re-subset them.
"""

from __future__ import annotations

import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "app" / "static" / "fonts"
CSS = ROOT / "app" / "static" / "css" / "fonts.css"

# latin + latin-ext only: enough for en, de-CH, fr-CH and it-CH.
SUBSETS = ("latin", "latin-ext")
SOURCES = (
    "https://fonts.googleapis.com/css2?family=Chivo:wght@400;700;900&display=swap",
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500;600&display=swap",
)
# Google serves woff2 only to browsers that advertise support.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

HEADER = """/* Self-hosted webfonts — no CDN at runtime, so the demo works offline.
   Chivo (display) + IBM Plex Sans (body) + IBM Plex Mono (labels, numerals).
   latin + latin-ext subsets only: covers en, de-CH, fr-CH, it-CH.
   Regenerate with scripts/fetch_fonts.py. */
"""


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA})
    ).read()


def fetch() -> int:
    FONTS.mkdir(parents=True, exist_ok=True)
    blocks = [HEADER]
    count = 0
    for source in SOURCES:
        css = _get(source).decode("utf-8")
        for match in re.finditer(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, re.S):
            subset, body = match.group(1), match.group(2)
            if subset not in SUBSETS:
                continue
            family = re.search(r"font-family:\s*'([^']+)'", body).group(1)
            weight = re.search(r"font-weight:\s*(\d+)", body).group(1)
            url = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
            unicode_range = re.search(r"unicode-range:\s*([^;]+);", body).group(1).strip()

            name = f"{family.lower().replace(' ', '-')}-{weight}-{subset}.woff2"
            (FONTS / name).write_bytes(_get(url))
            count += 1
            blocks.append(
                f"@font-face {{\n  font-family: '{family}';\n  font-style: normal;\n"
                f"  font-weight: {weight};\n  font-display: swap;\n"
                f"  src: url('../fonts/{name}') format('woff2');\n"
                f"  unicode-range: {unicode_range};\n}}\n"
            )
    CSS.write_text("\n".join(blocks), encoding="utf-8")
    return count


if __name__ == "__main__":
    print(f"Wrote {fetch()} font files to {FONTS} and regenerated {CSS.name}")
