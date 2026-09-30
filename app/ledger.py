from __future__ import annotations

import collections
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "verification_ledger.json"


def load_ledger(path: pathlib.Path = LEDGER_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(data: dict, path: pathlib.Path = LEDGER_PATH) -> None:
    """Write atomically: the agent mutates this file live on stage, and a truncating
    write interrupted mid-flight would leave unparseable JSON with no recovery path."""
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def add_order(
    txn_id: str,
    key: str,
    locale: str,
    word_count: int,
    amount: float,
    currency: str,
    submitted_at: str,
    path: pathlib.Path = LEDGER_PATH,
) -> dict:
    data = load_ledger(path)
    if any(o["txn_id"] == txn_id for o in data["orders"]):
        raise ValueError(f"order {txn_id} already exists")
    order = {
        "txn_id": txn_id,
        "key": key,
        "locale": locale,
        "word_count": word_count,
        "cost": {"amount": amount, "currency": currency},
        "status": "in_progress",
        "submitted_at": submitted_at,
        "completed_at": None,
    }
    data["orders"].append(order)
    save_ledger(data, path)
    return order


def close_order(txn_id: str, completed_at: str, path: pathlib.Path = LEDGER_PATH) -> dict:
    data = load_ledger(path)
    for order in data["orders"]:
        if order["txn_id"] == txn_id:
            order["status"] = "completed"
            order["completed_at"] = completed_at
            save_ledger(data, path)
            return order
    raise KeyError(f"no order with txn_id {txn_id}")


def spend_summary(path: pathlib.Path = LEDGER_PATH) -> dict:
    data = load_ledger(path)
    committed: collections.Counter[str] = collections.Counter()
    open_count = closed_count = 0
    for order in data["orders"]:
        committed[order["cost"]["currency"]] += order["cost"]["amount"]
        if order["status"] == "completed":
            closed_count += 1
        else:
            open_count += 1
    return {
        "budget": data["budget"],
        "committed": {c: round(v, 2) for c, v in committed.items()},
        "open": open_count,
        "closed": closed_count,
    }


def main() -> None:
    summary = spend_summary()
    budget = summary["budget"]
    print(f"Budget:    {budget['amount']:.2f} {budget['currency']}")
    if summary["committed"]:
        for currency, amount in sorted(summary["committed"].items()):
            print(f"Committed: {amount:.2f} {currency}")
    else:
        print("Committed: nothing yet")
    print(f"Orders:    {summary['open']} open, {summary['closed']} completed")


if __name__ == "__main__":
    main()
