"""Quick timers — sugar over the reminder system so they fire via the same scheduler."""
from __future__ import annotations
from . import reminders as _reminders


def set_timer(minutes: float = 0, seconds: float = 0, label: str = "Timer", lang: str = "en") -> str:
    """Set a countdown timer. Fires as a normal (one-shot) reminder."""
    try:
        total_seconds = int(float(minutes) * 60 + float(seconds))
    except (TypeError, ValueError):
        return "Invalid timer duration."
    if total_seconds <= 0:
        return "Timer needs a positive duration."

    when = f"in {total_seconds} seconds"
    text = label or "Timer"
    result = _reminders.add_reminder(text, when, lang=lang, recurrence="once")
    mins = total_seconds // 60
    secs = total_seconds % 60
    human = (f"{mins} min " if mins else "") + (f"{secs} sec" if secs else "")
    return f"Timer set for {human.strip()} — '{text}'. ({result})"
