"""Proactive heads-up: fires a 'You have X in N minutes' toast before reminders.

Reads `data/reminders.json` periodically. For each pending reminder, if it's
about to fire within proactive_lead_minutes, emit a one-time pre-toast.
Tracks which reminder IDs have already been pre-notified to avoid spam.
"""
from __future__ import annotations
import datetime as _dt
import json
import threading
from pathlib import Path
from typing import Callable

from .config import REMINDERS_FILE, DATA_DIR
from . import settings as _settings

_PRENOTIFY_FILE = Path(DATA_DIR) / "prenotified.json"
_lock = threading.Lock()


def _load_prenotified() -> dict:
    if not _PRENOTIFY_FILE.exists():
        return {}
    try:
        return json.loads(_PRENOTIFY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_prenotified(data: dict) -> None:
    try:
        _PRENOTIFY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[proactive] save failed: {e}")


def _load_reminders() -> list[dict]:
    p = Path(REMINDERS_FILE)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


class ProactiveScheduler(threading.Thread):
    """Fires pre-toast notifications for reminders/events about to occur."""

    def __init__(self, on_prenotify: Callable[[dict, int], None],
                 check_every: float = 30.0) -> None:
        super().__init__(daemon=True)
        self.on_prenotify = on_prenotify
        self.check_every = check_every
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[proactive] tick error: {e}")
            self._stop.wait(self.check_every)

    def _tick(self) -> None:
        lead_min = int(_settings.get("proactive_lead_minutes", 10) or 10)
        if lead_min <= 0:
            return
        now = _dt.datetime.now()
        ahead = now + _dt.timedelta(minutes=lead_min)

        with _lock:
            prenoted = _load_prenotified()
            items = _load_reminders()
            changed = False
            for r in items:
                rid = r.get("id")
                if not rid or r.get("fired"):
                    continue
                if prenoted.get(rid) == r.get("due_iso"):
                    # Already pre-notified for this due time (handles recurrences re-arming).
                    continue
                try:
                    due = _dt.datetime.fromisoformat(r["due_iso"])
                except Exception:
                    continue
                # Window: between now+1min and now+lead_min.
                if now + _dt.timedelta(minutes=1) <= due <= ahead:
                    mins = max(1, int((due - now).total_seconds() // 60))
                    try:
                        self.on_prenotify(r, mins)
                    except Exception as e:
                        print(f"[proactive] callback error: {e}")
                    prenoted[rid] = r["due_iso"]
                    changed = True
            if changed:
                _save_prenotified(prenoted)

    def stop(self) -> None:
        self._stop.set()
