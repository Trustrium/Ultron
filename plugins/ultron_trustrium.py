"""Ultron Trustrium plugin — briefing + project shortcuts for Rashid Ali.

Safe by design: read-only + open-folder only. No delete, no secrets, no sends.
Follows the plugins/README contract: TOOLS + HANDLERS, plain-string returns.
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import subprocess
from pathlib import Path

PROJECTS = {
    "mobogravity": ["MoboGravity", "mobogravity", "Mobogravity"],
    "shadow arena": ["shadow-arena-core", "ShadowArenaCore", "shadow-arena"],
    "shadowarena": ["shadow-arena-core", "ShadowArenaCore", "shadow-arena"],
    "time and tide": ["time-and-tide", "TimeAndTide", "time-and-tide-trailer"],
    "time & tide": ["time-and-tide", "TimeAndTide"],
    "bulk downloader": ["bulk-downloader", "BulkDownloader"],
    "bulk-downloader": ["bulk-downloader"],
    "echo protocol": ["echo-protocol", "EchoProtocol"],
    "trustrium": ["Trustrium", "trustrium"],
}

SEARCH_ROOTS = [
    Path.home() / "workspace",
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home(),
    Path.cwd(),
]


def _find_project_dir(project: str) -> Path | None:
    key = (project or "").strip().lower()
    candidates = PROJECTS.get(key, [key.replace(" ", "-"), key.replace(" ", "_")])
    # Also try the raw name as a folder.
    if key not in PROJECTS:
        candidates = [project.strip(), key.replace(" ", "-")]
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for name in candidates:
            p = root / name
            if p.is_dir():
                return p
        # One level deeper under workspace (e.g. ~/workspace/<project>)
        if root.name == "workspace":
            for child in root.iterdir():
                if child.is_dir() and child.name.lower() in [c.lower() for c in candidates]:
                    return child
    return None


def _reminders_count() -> int:
    try:
        f = Path(__file__).resolve().parent.parent / "data" / "reminders.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                return len(data)
    except Exception:
        pass
    return 0


def _system_health() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(str(Path.home())).percent
        return f"CPU {cpu:.0f}%, RAM {mem:.0f}%, Disk {disk:.0f}%"
    except Exception:
        return "System health unavailable (psutil not installed)."


def ultron_briefing_handler(args: dict) -> str:
    now = _dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p")
    health = _system_health()
    rem = _reminders_count()
    return (
        f"Ultron briefing, sir — {now}. {health}. "
        f"You have {rem} reminder(s) stored. "
        "Say 'open Trustrium project' to jump into MoboGravity, Shadow Arena, TIME & TIDE or bulk-downloader."
    )


def open_trustrium_project_handler(args: dict) -> str:
    project = (args.get("project") or "").strip()
    if not project:
        return "Which Trustrium project, sir? MoboGravity, Shadow Arena, TIME & TIDE, bulk-downloader, or Echo Protocol."
    found = _find_project_dir(project)
    if not found:
        return (
            f"I could not find a local folder for '{project}', sir. "
            "I searched workspace, Documents and Desktop. "
            "If the project lives elsewhere, tell me its folder path and I will open it."
        )
    try:
        if os.name == "nt":
            os.startfile(str(found))  # type: ignore[attr-defined]
        elif os.name == "posix":
            subprocess.Popen(["xdg-open", str(found)])
        return f"Opening {project} folder, sir: {found}"
    except Exception as e:
        return f"Found {found} but could not open it: {e}"


def trustrium_status_handler(args: dict) -> str:
    project = (args.get("project") or "").strip()
    targets: list[tuple[str, Path]] = []
    if project:
        found = _find_project_dir(project)
        if not found:
            return f"No local folder found for '{project}', sir."
        targets = [(project, found)]
    else:
        for name in ("MoboGravity", "Shadow Arena", "TIME & TIDE", "bulk-downloader"):
            found = _find_project_dir(name)
            if found:
                targets.append((name, found))
    if not targets:
        return "No Trustrium project folders found locally, sir."
    lines: list[str] = []
    for name, folder in targets:
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(folder), capture_output=True, text=True, timeout=5,
            )
            out = (r.stdout or "").strip()
            if not out:
                lines.append(f"{name}: clean (no changes).")
            else:
                first = out.splitlines()[0][:120]
                rest = len(out.splitlines()) - 1
                lines.append(f"{name}: {first}" + (f" (+{rest} more lines)" if rest > 0 else ""))
        except FileNotFoundError:
            lines.append(f"{name}: git not installed, cannot check status.")
        except Exception as e:
            lines.append(f"{name}: status check failed: {e}")
    return "Trustrium status, sir — " + " | ".join(lines)


TOOLS = [
    {
        "name": "ultron_briefing",
        "description": "Give Rashid a short daily briefing: date/time, system health, reminder count.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "open_trustrium_project",
        "description": "Open a Trustrium project folder on this PC. Projects: MoboGravity, Shadow Arena, TIME & TIDE, bulk-downloader, Echo Protocol, Trustrium.",
        "parameters": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "Project name, e.g. MoboGravity."}},
            "required": ["project"],
        },
    },
    {
        "name": "trustrium_status",
        "description": "Show git status (branch + dirty files) for one Trustrium project, or all found projects if project is empty. Read-only.",
        "parameters": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "Optional project name; empty means all found projects."}},
        },
    },
]

HANDLERS = {
    "ultron_briefing": ultron_briefing_handler,
    "open_trustrium_project": open_trustrium_project_handler,
    "trustrium_status": trustrium_status_handler,
}
