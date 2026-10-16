"""Journal — dated personal journal entries you can write + read back.

Stored in data/journal.json: [{date_iso, text}]
"""
from __future__ import annotations
import json
import threading
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

JOURNAL_FILE = Path(DATA_DIR) / "journal.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    try:
        return json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    JOURNAL_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def add_journal_entry(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "What would you like to journal?"
    with _lock:
        items = _load()
        items.append({"date_iso": _dt.datetime.now().isoformat(timespec="seconds"), "text": text})
        _save(items)
    return "Journal entry saved."


def read_journal(when: str = "recent", count: int = 5) -> str:
    """Read entries: 'recent' (last N), 'today', or a date 'YYYY-MM-DD'."""
    items = _load()
    if not items:
        return "Your journal is empty."
    when = (when or "recent").lower().strip()

    if when == "today":
        today = _dt.date.today().isoformat()
        sel = [e for e in items if e["date_iso"].startswith(today)]
    elif len(when) == 10 and when[4] == "-":
        sel = [e for e in items if e["date_iso"].startswith(when)]
    else:
        sel = items[-max(1, int(count)):]

    if not sel:
        return f"No journal entries for '{when}'."
    lines = []
    for e in sel:
        d = e["date_iso"][:16].replace("T", " ")
        lines.append(f"— {d}\n  {e['text']}")
    return "Journal:\n" + "\n".join(lines)
