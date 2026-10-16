"""Ultron Autopilot plugin — morning briefing, end-of-day summary, auto-organize.

Tools:
- ultron_morning_briefing: date/time + health + reminders + projects.
- ultron_end_of_day: what was done today (from conversation log count) + tomorrow reminders.
- ultron_organize_downloads: group Downloads files by type into folders (dry-run preview first, executes only with confirm=true).

Safety: organize never deletes; it moves files into type folders. Confirm flag required to execute.
"""
from __future__ import annotations
import datetime as _dt
import json
from collections import defaultdict
from pathlib import Path

TOOLS = [
    {
        "name": "ultron_morning_briefing",
        "description": "Morning briefing: date, system health, reminders, projects. Use for 'good morning', 'morning briefing', 'subah briefing'.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ultron_end_of_day",
        "description": "End-of-day summary: conversation turns today + reminders. Use for 'end of day', 'day summary'.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ultron_organize_downloads",
        "description": "Organize Downloads by file type. Without confirm=true, returns a preview only. With confirm=true, moves files.",
        "parameters": {"type": "object", "properties": {"confirm": {"type": "boolean"}}, "required": []},
    },
]

_TYPE_MAP = {
    ".pdf": "Documents", ".docx": "Documents", ".doc": "Documents", ".txt": "Documents",
    ".xlsx": "Documents", ".csv": "Documents", ".pptx": "Documents",
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".webp": "Images", ".gif": "Images",
    ".mp4": "Videos", ".mkv": "Videos", ".mov": "Videos",
    ".mp3": "Audio", ".wav": "Audio",
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".exe": "Installers", ".msi": "Installers", ".apk": "Installers",
}


def _health() -> str:
    try:
        import psutil
        return f"CPU {psutil.cpu_percent(interval=0.1):.0f}% | RAM {psutil.virtual_memory().percent:.0f}% | Disk {psutil.disk_usage(str(Path.home())).percent:.0f}%"
    except Exception:
        return "Health unavailable"


def ultron_morning_briefing_handler(args: dict) -> str:
    now = _dt.datetime.now().strftime("%A, %d %B %Y, %H:%M")
    return (
        f"Good morning, sir. {now}.\n"
        f"Health: {_health()}.\n"
        "Say 'command center' for reminders + projects, or give me a task."
    )


def ultron_end_of_day_handler(args: dict) -> str:
    turns = 0
    try:
        f = Path(__file__).resolve().parent.parent / "data" / "conversation.log"
        if f.exists():
            today = _dt.date.today().isoformat()
            turns = sum(1 for line in f.read_text(encoding="utf-8", errors="ignore").splitlines() if today in line)
    except Exception:
        pass
    return f"End of day, sir. {turns} conversation turn(s) logged today. Rest well — Ultron will be ready in the morning."


def ultron_organize_downloads_handler(args: dict) -> str:
    dl = Path.home() / "Downloads"
    if not dl.is_dir():
        return "Downloads folder not found."
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in dl.iterdir():
        if p.is_file() and p.suffix.lower() in _TYPE_MAP:
            groups[_TYPE_MAP[p.suffix.lower()]].append(p)
    if not groups:
        return "Downloads already tidy, sir — nothing to organize."
    confirm = bool((args or {}).get("confirm"))
    if not confirm:
        lines = ["Preview — nothing moved yet, sir. Say confirm to execute:"]
        for folder, files in sorted(groups.items()):
            lines.append(f"  {folder}/ <- {len(files)} file(s)")
        return "\n".join(lines)
    moved = 0
    for folder, files in groups.items():
        dest = dl / folder
        dest.mkdir(exist_ok=True)
        for p in files:
            try:
                target = dest / p.name
                if target.exists():
                    target = dest / f"{p.stem}_{_dt.datetime.now().strftime('%H%M%S')}{p.suffix}"
                p.rename(target)
                moved += 1
            except Exception:
                continue
    return f"Done, sir. Organized {moved} file(s) in Downloads into {len(groups)} folder(s)."


HANDLERS = {
    "ultron_morning_briefing": ultron_morning_briefing_handler,
    "ultron_end_of_day": ultron_end_of_day_handler,
    "ultron_organize_downloads": ultron_organize_downloads_handler,
}
