"""Expense tracker — log spending + see summaries by category / period.

Stored in data/expenses.json: [{id, amount, category, note, date_iso}]
"""
from __future__ import annotations
import json
import threading
import uuid
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

EXPENSES_FILE = Path(DATA_DIR) / "expenses.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not EXPENSES_FILE.exists():
        return []
    try:
        return json.loads(EXPENSES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    EXPENSES_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def log_expense(amount: float, category: str = "general", note: str = "") -> str:
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return f"Invalid amount: {amount}"
    category = (category or "general").lower().strip()
    item = {
        "id": uuid.uuid4().hex[:6],
        "amount": amt, "category": category, "note": note,
        "date_iso": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    return f"Logged {amt:g} for {category}" + (f" ({note})" if note else "")


def expense_summary(period: str = "month") -> str:
    """Summary by category for 'today' | 'week' | 'month' | 'all'."""
    items = _load()
    if not items:
        return "No expenses logged yet."
    now = _dt.datetime.now()
    period = (period or "month").lower().strip()

    def in_period(iso: str) -> bool:
        try:
            d = _dt.datetime.fromisoformat(iso)
        except Exception:
            return False
        if period == "today":
            return d.date() == now.date()
        if period == "week":
            return (now - d).days < 7
        if period == "month":
            return d.year == now.year and d.month == now.month
        return True  # all

    rows = [e for e in items if in_period(e.get("date_iso", ""))]
    if not rows:
        return f"No expenses in this {period}."
    by_cat: dict[str, float] = {}
    total = 0.0
    for e in rows:
        by_cat[e["category"]] = by_cat.get(e["category"], 0.0) + e["amount"]
        total += e["amount"]
    lines = [f"Expenses ({period}): total {total:g}"]
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {amt:g}")
    return "\n".join(lines)
