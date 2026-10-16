"""Shopping list — add / check off / remove items.

Stored in data/shopping.json: [{item, qty, done}]
"""
from __future__ import annotations
import json
import threading
from pathlib import Path

from ..config import DATA_DIR

SHOPPING_FILE = Path(DATA_DIR) / "shopping.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not SHOPPING_FILE.exists():
        return []
    try:
        return json.loads(SHOPPING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    SHOPPING_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def add_shopping_item(item: str, qty: str = "") -> str:
    item = (item or "").strip()
    if not item:
        return "What should I add to the list?"
    with _lock:
        items = _load()
        for it in items:
            if it["item"].lower() == item.lower():
                if qty:
                    it["qty"] = qty
                _save(items)
                return f"'{item}' is already on the list."
        items.append({"item": item, "qty": qty, "done": False})
        _save(items)
    return f"Added to shopping list: {item}" + (f" ({qty})" if qty else "")


def list_shopping() -> str:
    items = _load()
    if not items:
        return "Shopping list is empty."
    lines = []
    for it in items:
        mark = "x" if it.get("done") else " "
        q = f" ({it['qty']})" if it.get("qty") else ""
        lines.append(f"[{mark}] {it['item']}{q}")
    return "Shopping list:\n" + "\n".join(lines)


def check_shopping_item(item: str) -> str:
    q = (item or "").lower().strip()
    with _lock:
        items = _load()
        for it in items:
            if q in it["item"].lower():
                it["done"] = True
                _save(items)
                return f"Checked off: {it['item']}"
    return f"'{item}' not on the list."


def remove_shopping_item(item: str) -> str:
    q = (item or "").lower().strip()
    with _lock:
        items = _load()
        before = len(items)
        items = [it for it in items if q not in it["item"].lower()]
        _save(items)
    return "Removed." if len(items) < before else f"'{item}' not on the list."


def clear_shopping() -> str:
    with _lock:
        _save([])
    return "Shopping list cleared."
