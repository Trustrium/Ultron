"""Smart scheduling — find free time slots in the Google Calendar for a day.

Reuses the calendar OAuth from calendar_gcal. Working hours default 09:00-21:00.
"""
from __future__ import annotations
import datetime as _dt


def find_free_time(date: str = "today", work_start: str = "09:00",
                   work_end: str = "21:00", min_slot_minutes: int = 30) -> str:
    """List free gaps on a given day between working hours."""
    # Resolve date
    today = _dt.date.today()
    d = today
    ds = (date or "today").lower().strip()
    if ds == "tomorrow":
        d = today + _dt.timedelta(days=1)
    elif ds not in ("today", ""):
        try:
            d = _dt.date.fromisoformat(ds)
        except ValueError:
            return f"Couldn't parse date '{date}'. Use 'today', 'tomorrow', or YYYY-MM-DD."

    try:
        sh, sm = map(int, work_start.split(":"))
        eh, em = map(int, work_end.split(":"))
    except Exception:
        sh, sm, eh, em = 9, 0, 21, 0

    day_start = _dt.datetime.combine(d, _dt.time(sh, sm)).astimezone()
    day_end = _dt.datetime.combine(d, _dt.time(eh, em)).astimezone()

    # Pull events for the day
    try:
        from .calendar_gcal import _service
        svc = _service()
        resp = svc.events().list(
            calendarId="primary",
            timeMin=day_start.isoformat(), timeMax=day_end.isoformat(),
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = resp.get("items", [])
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar read failed: {e}"

    # Build busy intervals
    busy = []
    for ev in events:
        s = ev.get("start", {}).get("dateTime")
        e = ev.get("end", {}).get("dateTime")
        if not s or not e:
            continue  # skip all-day events
        try:
            busy.append((_dt.datetime.fromisoformat(s), _dt.datetime.fromisoformat(e)))
        except Exception:
            continue
    busy.sort()

    # Compute gaps
    free = []
    cursor = day_start
    for s, e in busy:
        if s > cursor:
            gap = (s - cursor).total_seconds() / 60
            if gap >= min_slot_minutes:
                free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < day_end:
        gap = (day_end - cursor).total_seconds() / 60
        if gap >= min_slot_minutes:
            free.append((cursor, day_end))

    label = d.strftime("%A %d %b")
    if not free:
        return f"No free slots ≥ {min_slot_minutes} min on {label} (between {work_start}-{work_end})."
    lines = [f"Free time on {label}:"]
    for s, e in free:
        mins = int((e - s).total_seconds() / 60)
        lines.append(f"  {s.strftime('%I:%M %p').lstrip('0')} – {e.strftime('%I:%M %p').lstrip('0')}  ({mins} min)")
    return "\n".join(lines)
