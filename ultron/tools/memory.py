"""Long-term memory store. Ultron can save facts and recall them across sessions.

Stored as a list of dicts in data/memory.json:
    {id, key, value, created_iso}
"""
import json
import uuid
import datetime as _dt
import threading

from ..config import MEMORY_FILE

_lock = threading.Lock()


def _load() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    MEMORY_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def remember(key: str, value: str) -> str:
    """Save (or update) a fact. Key is a short label, value is the content."""
    key = key.strip().lower()
    with _lock:
        items = _load()
        for r in items:
            if r["key"] == key:
                r["value"] = value
                r["updated_iso"] = _dt.datetime.now().isoformat(timespec="seconds")
                _save(items)
                return f"Updated memory for '{key}'."
        items.append({
            "id": uuid.uuid4().hex[:8],
            "key": key,
            "value": value,
            "created_iso": _dt.datetime.now().isoformat(timespec="seconds"),
        })
        _save(items)
    return f"Saved memory for '{key}'."


def recall(key: str | None = None) -> str:
    """Recall a fact by key, or list all if no key given."""
    items = _load()
    if not items:
        return "I don't remember anything yet."
    if key:
        key = key.strip().lower()
        for r in items:
            if r["key"] == key:
                return f"{r['key']}: {r['value']}"
        return f"I don't have a memory for '{key}'."
    lines = [f"- {r['key']}: {r['value']}" for r in items]
    return "Here's what I remember:\n" + "\n".join(lines)


def forget(key: str) -> str:
    key = key.strip().lower()
    with _lock:
        items = _load()
        before = len(items)
        items = [r for r in items if r["key"] != key]
        _save(items)
    return "Forgotten." if len(items) < before else f"No memory found for '{key}'."


def memory_summary_for_prompt(max_chars: int = 1200) -> str:
    """Compact rendering of memory for injection into the system prompt."""
    items = _load()
    if not items:
        return ""
    lines = [f"- {r['key']}: {r['value']}" for r in items]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text
