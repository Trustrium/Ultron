"""Ultron Command Center plugin — one command, full picture.

Tools:
- ultron_command_center: system health + reminders + projects + profile summary.
- ultron_plan: turn any natural command into an Ultron Commander plan (dry-run, no execution).
- ultron_memory_summary: who sir is, his projects and style (from Ultron Memory).

Safe: read-only. No delete, no sends, no shell.
"""
from __future__ import annotations
import json
from pathlib import Path

TOOLS = [
    {
        "name": "ultron_command_center",
        "description": "Show the Ultron Command Center: system health, reminders count, Trustrium projects, and user profile. Use when sir asks 'status', 'briefing', 'command center', 'kya haal hai'.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ultron_plan",
        "description": "Turn a natural command into a step-by-step Ultron plan (dry-run, does NOT execute). Use when sir asks 'plan this' or to preview a risky task.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "ultron_memory_summary",
        "description": "Summarize what Ultron remembers about sir: name, company, languages, projects, style.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


def _health() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(str(Path.home())).percent
        return f"CPU {cpu:.0f}% | RAM {mem:.0f}% | Disk {disk:.0f}%"
    except Exception:
        return "System health unavailable (psutil not installed)."


def _reminders() -> str:
    try:
        f = Path(__file__).resolve().parent.parent / "data" / "reminders.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            n = len(data) if isinstance(data, (list, dict)) else 0
            return f"{n} reminder(s)"
    except Exception:
        pass
    return "0 reminder(s)"


def ultron_command_center_handler(args: dict) -> str:
    try:
        from ultron.memory.profile import load_profile, get_profile_summary
        profile = get_profile_summary(load_profile())
    except Exception as e:
        profile = f"Profile unavailable: {e}"
    return (
        "ULTRON COMMAND CENTER\n"
        f"Health: {_health()}\n"
        f"Reminders: {_reminders()}\n"
        f"{profile}"
    )


def ultron_plan_handler(args: dict) -> str:
    try:
        from ultron.core.commander import parse_command, format_plan
        plan = parse_command((args or {}).get("command", ""))
        return format_plan(plan)
    except Exception as e:
        return f"Plan failed: {e}"


def ultron_memory_summary_handler(args: dict) -> str:
    try:
        from ultron.memory.profile import load_profile, get_profile_summary
        return get_profile_summary(load_profile())
    except Exception as e:
        return f"Memory unavailable: {e}"


HANDLERS = {
    "ultron_command_center": ultron_command_center_handler,
    "ultron_plan": ultron_plan_handler,
    "ultron_memory_summary": ultron_memory_summary_handler,
}
