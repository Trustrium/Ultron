"""Proactive insights — Ultron anticipates and speaks up on its own.

A background thread periodically evaluates light rules over the user's data
(tasks, habits, reminders) and surfaces AT MOST one helpful nudge, time-gated and
de-duplicated so it's never spammy. Each rule fires at most once per day.

Rules:
  - morning briefing offer       (08:00-10:00)
  - habit streak at risk         (18:00-22:00, a habit not done today)
  - pending high-priority tasks  (12:00-18:00)
"""
from __future__ import annotations
import datetime as _dt
import json
import threading
from pathlib import Path
from typing import Callable

from .config import DATA_DIR
from . import settings as _settings

_STATE_FILE = Path(DATA_DIR) / "insights_state.json"
_lock = threading.Lock()


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(d: dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception:
        pass


def _fired_today(rule: str) -> bool:
    return _load_state().get(rule) == _dt.date.today().isoformat()


def _mark_fired(rule: str) -> None:
    with _lock:
        d = _load_state()
        d[rule] = _dt.date.today().isoformat()
        _save_state(d)


def _evaluate() -> str | None:
    """Return one insight string to surface, or None."""
    now = _dt.datetime.now()
    h = now.hour

    # 1) Morning briefing offer
    if 8 <= h < 10 and not _fired_today("morning"):
        _mark_fired("morning")
        try:
            from .tools.profile import profile_for_prompt
            name = ""
            prof = profile_for_prompt()
            if prof.startswith("name:"):
                name = " " + prof.split(";", 1)[0].replace("name:", "").strip()
        except Exception:
            name = ""
        return f"Good morning{name}. Would you like your daily briefing?"

    # 2) Habit streak at risk (evening)
    if 18 <= h < 22 and not _fired_today("habit_risk"):
        try:
            from .tools import habits as H
            d = H._load()
            today = _dt.date.today().isoformat()
            at_risk = [(name, H._streak(info["done_dates"]))
                       for name, info in d.items()
                       if today not in info.get("done_dates", []) and H._streak(info["done_dates"]) >= 1]
            if at_risk:
                _mark_fired("habit_risk")
                name, streak = at_risk[0]
                return (f"Heads up — you haven't done '{name}' today. "
                        f"Keep your {streak}-day streak alive!")
        except Exception:
            pass

    # 3) Pending high-priority tasks (midday)
    if 12 <= h < 18 and not _fired_today("tasks"):
        try:
            from .tools import tasks as T
            items = [t for t in T._load() if not t.get("done") and t.get("priority") == "high"]
            if items:
                _mark_fired("tasks")
                n = len(items)
                return (f"Reminder: you have {n} high-priority "
                        f"task{'s' if n != 1 else ''} still pending.")
        except Exception:
            pass

    return None


class InsightEngine(threading.Thread):
    """Surfaces proactive nudges via on_insight(text)."""

    def __init__(self, on_insight: Callable[[str], None], check_every: float = 300.0):
        super().__init__(daemon=True)
        self.on_insight = on_insight
        self.check_every = check_every
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                if _settings.get("proactive_insights", True):
                    msg = _evaluate()
                    if msg:
                        self.on_insight(msg)
            except Exception as e:
                print(f"[insights] error: {e}")
            self._stop.wait(self.check_every)

    def stop(self) -> None:
        self._stop.set()
