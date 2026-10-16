"""Pomodoro focus sessions — schedule work/break transitions via the reminder system.

Each transition fires as a normal reminder (toast + voice) through the running
scheduler, so no extra background machinery is needed.
"""
from __future__ import annotations
from . import reminders as _reminders


def start_pomodoro(work_minutes: int = 25, break_minutes: int = 5,
                   cycles: int = 4, lang: str = "en") -> str:
    """Schedule a Pomodoro chain: (work -> break) x cycles."""
    try:
        work = max(1, min(int(work_minutes), 120))
        brk = max(1, min(int(break_minutes), 60))
        cyc = max(1, min(int(cycles), 8))
    except (TypeError, ValueError):
        return "Invalid Pomodoro parameters."

    elapsed = 0
    scheduled = 0
    for c in range(1, cyc + 1):
        elapsed += work
        _reminders.add_reminder(
            f"Pomodoro {c}: work block done — take a {brk} min break.",
            f"in {elapsed} minutes", lang=lang, recurrence="once",
        )
        scheduled += 1
        if c < cyc:
            elapsed += brk
            _reminders.add_reminder(
                f"Break over — start work block {c+1}.",
                f"in {elapsed} minutes", lang=lang, recurrence="once",
            )
            scheduled += 1
    total = elapsed
    return (f"Pomodoro started: {cyc} x ({work} min work + {brk} min break). "
            f"I'll nudge you at each transition. Total ~{total} min, {scheduled} alerts set.")
