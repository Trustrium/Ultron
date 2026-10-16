"""To-do tasks — a proper task list with priority + done state (distinct from reminders).

Stored in data/tasks.json: [{id, text, priority, done, created_iso, done_iso}]
"""
from __future__ import annotations
import json
import threading
import uuid
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

TASKS_FILE = Path(DATA_DIR) / "tasks.json"
_lock = threading.Lock()
_PRIORITY = {"low": 0, "normal": 1, "high": 2}


def _load() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    TASKS_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def add_task(text: str, priority: str = "normal") -> str:
    text = (text or "").strip()
    if not text:
        return "A task needs a description."
    priority = (priority or "normal").lower().strip()
    if priority not in _PRIORITY:
        priority = "normal"
    item = {
        "id": uuid.uuid4().hex[:6],
        "text": text,
        "priority": priority,
        "done": False,
        "created_iso": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    return f"Task added [{item['id']}, {priority}]: {text}"


def list_tasks(include_done: bool = False) -> str:
    items = _load()
    if not include_done:
        items = [t for t in items if not t.get("done")]
    if not items:
        return "No pending tasks. 🎉"
    items.sort(key=lambda t: (-_PRIORITY.get(t.get("priority", "normal"), 1), t.get("created_iso", "")))
    lines = []
    for t in items:
        mark = "x" if t.get("done") else " "
        pr = t.get("priority", "normal")
        tag = {"high": "‼ ", "low": "· ", "normal": ""}.get(pr, "")
        lines.append(f"[{mark}] ({t['id']}) {tag}{t['text']}")
    return "Tasks:\n" + "\n".join(lines)


def complete_task(task_id: str) -> str:
    tid = (task_id or "").strip().lower()
    with _lock:
        items = _load()
        for t in items:
            if t["id"] == tid or t["text"].lower() == tid:
                t["done"] = True
                t["done_iso"] = _dt.datetime.now().isoformat(timespec="seconds")
                _save(items)
                return f"Done: {t['text']}"
    return f"No task matching '{task_id}'."


def delete_task(task_id: str) -> str:
    tid = (task_id or "").strip().lower()
    with _lock:
        items = _load()
        before = len(items)
        items = [t for t in items if t["id"] != tid and t["text"].lower() != tid]
        _save(items)
    return "Task deleted." if len(items) < before else f"No task matching '{task_id}'."


def clear_done_tasks() -> str:
    with _lock:
        items = _load()
        kept = [t for t in items if not t.get("done")]
        removed = len(items) - len(kept)
        _save(kept)
    return f"Cleared {removed} completed task(s)."
