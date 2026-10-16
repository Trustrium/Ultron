"""Folder organizer — sort loose files into category subfolders by type.

e.g. organize Downloads -> Images/, Documents/, Videos/, Audio/, Archives/, Code/, Other/
"""
from __future__ import annotations
import shutil
from pathlib import Path

CATEGORIES = {
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".xls", ".xlsx",
                  ".csv", ".ppt", ".pptx"},
    "Videos":    {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"},
    "Audio":     {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"},
    "Code":      {".py", ".js", ".ts", ".java", ".c", ".cpp", ".html", ".css", ".json", ".sh"},
    "Installers":{".exe", ".msi", ".bat"},
}


def _category(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Other"


def organize_folder(folder: str, dry_run: bool = False) -> str:
    """Move loose files in `folder` into category subfolders. dry_run just reports the plan."""
    p = Path(folder).expanduser()
    if not p.exists() or not p.is_dir():
        return f"Not a folder: {p}"

    moves: dict[str, int] = {}
    planned: list[tuple[Path, Path]] = []
    for item in p.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        cat = _category(item.suffix)
        dest_dir = p / cat
        dest = dest_dir / item.name
        if dest == item:
            continue
        planned.append((item, dest))
        moves[cat] = moves.get(cat, 0) + 1

    if not planned:
        return f"Nothing to organize in {p}."

    if dry_run:
        plan = ", ".join(f"{c}: {n}" for c, n in sorted(moves.items()))
        return f"Plan for {p} ({len(planned)} files): {plan}"

    moved = 0
    for src, dest in planned:
        try:
            dest.parent.mkdir(exist_ok=True)
            # Avoid overwrite: add a counter if needed
            if dest.exists():
                i = 1
                while (dest.parent / f"{dest.stem} ({i}){dest.suffix}").exists():
                    i += 1
                dest = dest.parent / f"{dest.stem} ({i}){dest.suffix}"
            shutil.move(str(src), str(dest))
            moved += 1
        except Exception:
            continue
    summary = ", ".join(f"{c}: {n}" for c, n in sorted(moves.items()))
    return f"Organized {moved} files in {p} -> {summary}"
