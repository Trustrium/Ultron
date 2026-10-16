"""Habit tracker — define daily habits, check them off, track streaks.

Stored in data/habits.json: {name: {created_iso, done_dates: [YYYY-MM-DD, ...]}}
"""
from __future__ import annotations
import json
import threading
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

HABITS_FILE = Path(DATA_DIR) / "habits.json"
_lock = threading.Lock()


def _load() -> dict:
    if not HABITS_FILE.exists():
        return {}
    try:
        return json.loads(HABITS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    HABITS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _streak(done_dates: list[str]) -> int:
    """Current consecutive-day streak ending today or yesterday."""
    if not done_dates:
        return 0
    days = set(done_dates)
    streak = 0
    cur = _dt.date.today()
    # Allow today not yet done — count back from yesterday in that case.
    if cur.isoformat() not in days:
        cur = cur - _dt.timedelta(days=1)
    while cur.isoformat() in days:
        streak += 1
        cur -= _dt.timedelta(days=1)
    return streak


def add_habit(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "A habit needs a name."
    with _lock:
        d = _load()
        if name.lower() in {k.lower() for k in d}:
            return f"Habit '{name}' already exists."
        d[name] = {"created_iso": _dt.datetime.now().isoformat(timespec="seconds"), "done_dates": []}
        _save(d)
    return f"Habit added: {name}. Check it off each day to build a streak."


def check_habit(name: str) -> str:
    q = (name or "").lower().strip()
    today = _dt.date.today().isoformat()
    with _lock:
        d = _load()
        for k in d:
            if q in k.lower():
                if today in d[k]["done_dates"]:
                    return f"'{k}' already done today. Streak: {_streak(d[k]['done_dates'])} days 🔥"
                d[k]["done_dates"].append(today)
                _save(d)
                return f"Nice — '{k}' done! Streak: {_streak(d[k]['done_dates'])} days 🔥"
    return f"No habit matching '{name}'. Add it first."


def list_habits() -> str:
    d = _load()
    if not d:
        return "No habits yet. Add one to start building streaks."
    today = _dt.date.today().isoformat()
    lines = []
    for name, info in d.items():
        done_today = "✓" if today in info["done_dates"] else " "
        lines.append(f"[{done_today}] {name} — streak {_streak(info['done_dates'])} days")
    return "Habits:\n" + "\n".join(lines)


def delete_habit(name: str) -> str:
    q = (name or "").lower().strip()
    with _lock:
        d = _load()
        for k in list(d):
            if k.lower() == q:
                del d[k]
                _save(d)
                return f"Habit '{k}' deleted."
    return f"No habit named '{name}'."
