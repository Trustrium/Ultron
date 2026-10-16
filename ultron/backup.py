"""Export / import Ultron user data: settings, memories, reminders, notes, conversation log.

Produces a .zip file the user can move between machines.
"""
from __future__ import annotations
import json
import shutil
import zipfile
import datetime as _dt
from pathlib import Path

from .config import DATA_DIR
from . import settings as settings_mod

# What to include in a backup. Anything that isn't critical (gmail_token, wa_chrome_profile,
# whisper cache, etc.) is excluded.
INCLUDE_FILES = [
    "memory.json",
    "reminders.json",
    "notes.md",
    "conversation.log",
    "usage.json",
    "routines.json",
    "skills.json",
    "tasks.json",
    "contacts.json",
    "expenses.json",
    "shopping.json",
    "habits.json",
    "health.json",
    "journal.json",
]


def export_backup(out_path: str | Path) -> str:
    """Write a .zip backup to out_path. Returns the absolute path."""
    out = Path(out_path)
    if out.is_dir():
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = out / f"ultron_backup_{ts}.zip"
    if out.suffix != ".zip":
        out = out.with_suffix(".zip")

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # Settings — exported from the in-memory schema rather than file path
        s = settings_mod.load()
        zf.writestr("settings.json", json.dumps(s, indent=2, ensure_ascii=False))
        # Bundled data files
        for name in INCLUDE_FILES:
            src = Path(DATA_DIR) / name
            if src.exists():
                zf.write(src, arcname=f"data/{name}")
        # Manifest
        manifest = {
            "exported_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "files": [f"data/{n}" for n in INCLUDE_FILES if (Path(DATA_DIR) / n).exists()] + ["settings.json"],
            "version": "v4",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return str(out.resolve())


def import_backup(zip_path: str | Path, restore_settings: bool = True,
                  restore_data: bool = True) -> str:
    """Restore a backup zip. Existing files at target paths get overwritten."""
    src = Path(zip_path)
    if not src.exists():
        return f"Backup file not found: {src}"

    restored: list[str] = []
    try:
        with zipfile.ZipFile(src, "r") as zf:
            names = zf.namelist()

            if restore_settings and "settings.json" in names:
                content = zf.read("settings.json").decode("utf-8")
                try:
                    parsed = json.loads(content)
                    settings_mod.save(parsed)
                    restored.append("settings")
                except Exception as e:
                    return f"Bad settings.json in backup: {e}"

            if restore_data:
                for n in names:
                    if n.startswith("data/"):
                        target = Path(DATA_DIR) / Path(n).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(n) as src_f, open(target, "wb") as dst:
                            shutil.copyfileobj(src_f, dst)
                        restored.append(Path(n).name)
        return f"Restored: {', '.join(restored)} from {src.name}"
    except Exception as e:
        return f"Restore failed: {e}"
