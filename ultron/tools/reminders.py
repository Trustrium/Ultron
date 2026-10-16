"""Persistent reminders + background scheduler thread.

Stored in data/reminders.json as a list of:
    {id, text, due_iso, lang, created_iso, fired, recurrence}

`recurrence` is one of:
    None / "" / "once"     -> one-shot
    "daily"                -> every 24h at the same time
    "weekly"               -> every 7 days
    "weekdays"             -> Mon-Fri at the same time
    "monthly"              -> same day next month
    "yearly"               -> same date next year
"""
import json
import threading
import time
import uuid
import datetime as _dt
from typing import Callable

from ..config import REMINDERS_FILE

_lock = threading.Lock()


def _load() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    try:
        return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    REMINDERS_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ===== Time parsing =====

_WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _parse_due(when: str) -> _dt.datetime | None:
    """Parse natural-language or ISO datetime. Returns the FIRST occurrence."""
    when = when.strip().lower()
    now = _dt.datetime.now()

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(when, fmt)
        except ValueError:
            pass

    if when.startswith("in "):
        try:
            parts = when.split()
            n = int(parts[1])
            unit = parts[2]
            if "min" in unit:  return now + _dt.timedelta(minutes=n)
            if "hour" in unit: return now + _dt.timedelta(hours=n)
            if "day" in unit:  return now + _dt.timedelta(days=n)
            if "sec" in unit:  return now + _dt.timedelta(seconds=n)
        except Exception:
            pass

    base = None
    rest = when
    if when.startswith("tomorrow"):
        base = now + _dt.timedelta(days=1)
        rest = when.replace("tomorrow", "").strip()
    elif when.startswith("today"):
        base = now
        rest = when.replace("today", "").strip()
    else:
        # Day-of-week: "monday 9am", "fri 5pm"
        for name, weekday in _WEEKDAY_NAMES.items():
            if when.startswith(name):
                days_ahead = (weekday - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                base = now + _dt.timedelta(days=days_ahead)
                rest = when[len(name):].strip()
                break

    if base is not None:
        if not rest:
            return _dt.datetime.combine(base.date(), _dt.time(9, 0))
        for fmt in ("%I%p", "%I %p", "%I:%M%p", "%I:%M %p", "%H:%M"):
            try:
                t = _dt.datetime.strptime(rest, fmt).time()
                return _dt.datetime.combine(base.date(), t)
            except ValueError:
                pass

    # Bare time like "11am", "11:00 AM", "17:30" — pick today if future, else tomorrow.
    for fmt in ("%I%p", "%I %p", "%I:%M%p", "%I:%M %p", "%H:%M"):
        try:
            t = _dt.datetime.strptime(when.upper(), fmt).time()
            candidate = _dt.datetime.combine(now.date(), t)
            if candidate <= now:
                candidate += _dt.timedelta(days=1)
            return candidate
        except ValueError:
            pass

    return None


def _next_occurrence(due: _dt.datetime, recurrence: str) -> _dt.datetime | None:
    """Given a fired reminder, return the next fire time. None = no more fires."""
    r = (recurrence or "once").lower().strip()
    if r in {"", "once", "none"}:
        return None
    if r == "daily":
        return due + _dt.timedelta(days=1)
    if r == "weekly":
        return due + _dt.timedelta(weeks=1)
    if r == "weekdays":
        nxt = due + _dt.timedelta(days=1)
        # Skip weekends.
        while nxt.weekday() >= 5:
            nxt += _dt.timedelta(days=1)
        return nxt
    if r == "monthly":
        # Add one month, clamping the day if needed.
        month = due.month + 1
        year = due.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        from calendar import monthrange
        day = min(due.day, monthrange(year, month)[1])
        return due.replace(year=year, month=month, day=day)
    if r == "yearly":
        return due.replace(year=due.year + 1)
    return None


# ===== Public tool API =====

VALID_RECURRENCES = {"once", "daily", "weekly", "weekdays", "monthly", "yearly"}


def add_reminder(text: str, when: str, lang: str = "en", recurrence: str = "once") -> str:
    due = _parse_due(when)
    if due is None:
        return (f"Sorry, I couldn't parse the time '{when}'. "
                "Try '2026-05-17 09:30', 'in 30 minutes', 'tomorrow 9am', or 'monday 5pm'.")
    recurrence = (recurrence or "once").lower().strip()
    if recurrence not in VALID_RECURRENCES:
        return (f"Invalid recurrence '{recurrence}'. Must be one of: "
                f"{', '.join(sorted(VALID_RECURRENCES))}")
    item = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "due_iso": due.isoformat(timespec="seconds"),
        "lang": lang,
        "created_iso": _dt.datetime.now().isoformat(timespec="seconds"),
        "fired": False,
        "recurrence": recurrence,
    }
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    suffix = f" (recurring: {recurrence})" if recurrence != "once" else ""
    return f"Reminder set for {due.strftime('%a %d %b %I:%M %p')}{suffix} — {text}"


def list_reminders(include_fired: bool = False) -> str:
    items = _load()
    if not include_fired:
        items = [r for r in items if not r.get("fired")]
    if not items:
        return "You have no pending reminders."
    items.sort(key=lambda r: r["due_iso"])
    lines = []
    for r in items:
        due = _dt.datetime.fromisoformat(r["due_iso"])
        rec = r.get("recurrence", "once")
        rec_str = f" [{rec}]" if rec and rec != "once" else ""
        lines.append(f"- [{r['id']}] {due.strftime('%a %d %b %I:%M %p')}{rec_str}: {r['text']}")
    return "Pending reminders:\n" + "\n".join(lines)


def delete_reminder(reminder_id: str) -> str:
    with _lock:
        items = _load()
        before = len(items)
        items = [r for r in items if r["id"] != reminder_id]
        _save(items)
    return "Reminder deleted." if len(items) < before else f"No reminder with id {reminder_id}."


def reminders_due_today() -> list[dict]:
    """All non-fired reminders due before tomorrow midnight."""
    items = _load()
    today_end = _dt.datetime.combine(_dt.date.today() + _dt.timedelta(days=1), _dt.time(0, 0))
    out = []
    for r in items:
        if r.get("fired"):
            continue
        due = _dt.datetime.fromisoformat(r["due_iso"])
        if due <= today_end:
            out.append(r)
    out.sort(key=lambda r: r["due_iso"])
    return out


# ===== Background scheduler =====

class ReminderScheduler(threading.Thread):
    """Fires due reminders via callback. Recurring reminders auto-reschedule."""

    def __init__(self, on_fire: Callable[[dict], None], check_every: float = 20.0):
        super().__init__(daemon=True)
        self.on_fire = on_fire
        self.check_every = check_every
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[scheduler] error: {e}")
            self._stop.wait(self.check_every)

    def _tick(self) -> None:
        now = _dt.datetime.now()
        with _lock:
            items = _load()
            changed = False
            for r in items:
                if r.get("fired"):
                    continue
                due = _dt.datetime.fromisoformat(r["due_iso"])
                if due <= now:
                    try:
                        self.on_fire(r)
                    except Exception as e:
                        print(f"[scheduler] on_fire failed: {e}")
                    # Recurring? Bump due_iso to next occurrence instead of marking fired.
                    nxt = _next_occurrence(due, r.get("recurrence", "once"))
                    if nxt:
                        r["due_iso"] = nxt.isoformat(timespec="seconds")
                    else:
                        r["fired"] = True
                    changed = True
            if changed:
                _save(items)

    def stop(self) -> None:
        self._stop.set()
