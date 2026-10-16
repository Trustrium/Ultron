"""Scheduled autonomous routines — run the v10 agent on a cron-like schedule.

A routine = {name, goal, schedule, enabled, last_run}. Stored in data/routines.json.

Schedule types:
  {"type": "daily",  "time": "08:00"}
  {"type": "hourly"}                       # fires at minute 00 each hour
  {"type": "weekly", "day": "monday", "time": "09:00"}

A background RoutineScheduler thread checks each minute and fires due routines by
running agent.accomplish(goal), then hands the result to a callback (speak / toast).
"""
from __future__ import annotations
import datetime as _dt
import json
import threading
from pathlib import Path
from typing import Callable

from .config import DATA_DIR

ROUTINES_FILE = Path(DATA_DIR) / "routines.json"
_lock = threading.Lock()

_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}


def _load() -> dict:
    if not ROUTINES_FILE.exists():
        return {}
    try:
        return json.loads(ROUTINES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    ROUTINES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ===== Tool API =====

def create_routine(name: str, goal: str, schedule_type: str = "daily",
                   time: str = "08:00", day: str = "monday") -> str:
    name = (name or "").strip()
    goal = (goal or "").strip()
    if not name or not goal:
        return "A routine needs a name and a goal."
    schedule_type = (schedule_type or "daily").lower().strip()
    if schedule_type not in {"daily", "hourly", "weekly"}:
        return "schedule_type must be daily, hourly, or weekly."

    sched: dict = {"type": schedule_type}
    if schedule_type in ("daily", "weekly"):
        # Validate time HH:MM
        try:
            _dt.datetime.strptime(time, "%H:%M")
        except ValueError:
            return f"Invalid time '{time}'. Use 24h HH:MM (e.g. 08:00, 18:30)."
        sched["time"] = time
    if schedule_type == "weekly":
        d = (day or "").lower().strip()
        if d not in _WEEKDAYS:
            return f"Invalid day '{day}'. Use a weekday name."
        sched["day"] = d

    with _lock:
        data = _load()
        data[name] = {"goal": goal, "schedule": sched, "enabled": True, "last_run": ""}
        _save(data)
    when = (f"every day at {time}" if schedule_type == "daily"
            else f"every hour" if schedule_type == "hourly"
            else f"every {day} at {time}")
    return f"Routine '{name}' created — runs {when}: {goal}"


def list_routines() -> str:
    data = _load()
    if not data:
        return "No routines defined."
    lines = []
    for name, r in data.items():
        s = r.get("schedule", {})
        stype = s.get("type", "?")
        when = (f"daily {s.get('time','')}" if stype == "daily"
                else "hourly" if stype == "hourly"
                else f"{s.get('day','')} {s.get('time','')}")
        status = "on" if r.get("enabled", True) else "off"
        lines.append(f"- {name} [{status}, {when}]: {r.get('goal','')[:60]}")
    return "Routines:\n" + "\n".join(lines)


def delete_routine(name: str) -> str:
    with _lock:
        data = _load()
        if name not in data:
            return f"No routine named '{name}'."
        del data[name]
        _save(data)
    return f"Routine '{name}' deleted."


def set_routine_enabled(name: str, enabled: bool) -> str:
    with _lock:
        data = _load()
        if name not in data:
            return f"No routine named '{name}'."
        data[name]["enabled"] = bool(enabled)
        _save(data)
    return f"Routine '{name}' {'enabled' if enabled else 'disabled'}."


def run_routine_now(name: str) -> str:
    data = _load()
    if name not in data:
        return f"No routine named '{name}'."
    goal = data[name]["goal"]
    from .agent import accomplish
    return accomplish(goal, max_steps=12)


# ===== Scheduler =====

def _is_due(routine: dict, now: _dt.datetime) -> bool:
    if not routine.get("enabled", True):
        return False
    sched = routine.get("schedule", {})
    stype = sched.get("type")
    last = routine.get("last_run", "")

    if stype == "hourly":
        key = now.strftime("%Y-%m-%d %H")
        return last != key and now.minute == 0

    if stype == "daily":
        try:
            hh, mm = map(int, sched.get("time", "08:00").split(":"))
        except Exception:
            return False
        key = now.strftime("%Y-%m-%d")
        return last != key and (now.hour, now.minute) >= (hh, mm) and now.hour == hh and now.minute >= mm

    if stype == "weekly":
        day = sched.get("day", "monday")
        if _WEEKDAYS.get(day) != now.weekday():
            return False
        try:
            hh, mm = map(int, sched.get("time", "09:00").split(":"))
        except Exception:
            return False
        key = now.strftime("%Y-%W")   # year-week
        return last != key and now.hour == hh and now.minute >= mm

    return False


def _mark_ran(name: str, now: _dt.datetime, stype: str) -> None:
    with _lock:
        data = _load()
        if name not in data:
            return
        if stype == "hourly":
            data[name]["last_run"] = now.strftime("%Y-%m-%d %H")
        elif stype == "weekly":
            data[name]["last_run"] = now.strftime("%Y-%W")
        else:
            data[name]["last_run"] = now.strftime("%Y-%m-%d")
        _save(data)


class RoutineScheduler(threading.Thread):
    """Fires due routines by running the autonomous agent, then calls on_result(name, text)."""

    def __init__(self, on_result: Callable[[str, str], None], check_every: float = 60.0):
        super().__init__(daemon=True)
        self.on_result = on_result
        self.check_every = check_every
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[routines] tick error: {e}")
            self._stop.wait(self.check_every)

    def _tick(self) -> None:
        now = _dt.datetime.now()
        data = _load()
        for name, routine in data.items():
            if _is_due(routine, now):
                stype = routine.get("schedule", {}).get("type", "daily")
                self._mark_ran_safe(name, now, stype)
                goal = routine.get("goal", "")
                print(f"[routines] firing '{name}': {goal}")
                try:
                    from .agent import accomplish
                    result = accomplish(goal, max_steps=12)
                except Exception as e:
                    result = f"Routine '{name}' failed: {e}"
                try:
                    self.on_result(name, result)
                except Exception as e:
                    print(f"[routines] on_result error: {e}")

    def _mark_ran_safe(self, name, now, stype):
        try:
            _mark_ran(name, now, stype)
        except Exception as e:
            print(f"[routines] mark_ran error: {e}")

    def stop(self) -> None:
        self._stop.set()
