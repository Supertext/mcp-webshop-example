"""Return the repository to its pre-demo state. Run this before going on stage."""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.i18n import LOCALES_DIR, TARGET_LOCALES  # noqa: E402
from app.ledger import LEDGER_PATH, save_ledger  # noqa: E402
from scripts.seed_analytics import seed  # noqa: E402

BUDGET = {"amount": 100.00, "currency": "CHF"}


def _atomic_write(path: pathlib.Path, text: str) -> None:
    """Same discipline as save_ledger: the site hot-reloads these files mid-poll,
    and a truncating write interrupted mid-flight transiently 500s page renders."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def reset_locales(locales_dir: pathlib.Path = LOCALES_DIR) -> None:
    for locale in TARGET_LOCALES:
        payload = {"schema_version": 1, "locale": locale, "strings": {}}
        _atomic_write(
            locales_dir / f"{locale}.json",
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )


def reset_ledger(path: pathlib.Path = LEDGER_PATH) -> None:
    save_ledger({"budget": BUDGET, "orders": []}, path)


def reset() -> None:
    """Pre-demo state: locales empty, ledger clear, analytics seeded.

    The show's first move is `make translate`, which fills the locales live.
    Reset must therefore leave them empty; it never calls the API.
    """
    reset_locales()
    reset_ledger()
    total = seed()
    print("Locales emptied, ledger cleared.")
    print(f"Seeded {total:,} analytics events.")
    print("Ready for the demo: run `make translate` on stage to fill the locales.")


if __name__ == "__main__":
    reset()
