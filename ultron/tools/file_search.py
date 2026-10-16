"""Find files by name (and optionally grep content) across common user folders.

Scope: by default searches Desktop, Documents, Downloads. Caller can override.
Hard cap on results + walk depth to keep this snappy.
"""
from __future__ import annotations
import os
import re
from pathlib import Path

DEFAULT_DIRS = ["Desktop", "Documents", "Downloads"]
MAX_RESULTS = 25
MAX_FILES_SCANNED = 5000
MAX_BYTES_PER_FILE_FOR_GREP = 200_000   # don't grep huge files

SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__",
             "AppData", ".cache", "OneDriveTemp", ".idea", ".vscode"}


def _scope_dirs() -> list[Path]:
    home = Path.home()
    out: list[Path] = []
    for name in DEFAULT_DIRS:
        for candidate in (home / "OneDrive" / name, home / name):
            if candidate.exists():
                out.append(candidate)
                break
    return out


def find_files(name_pattern: str, content_query: str = "", max_results: int = MAX_RESULTS) -> str:
    """Find files whose name matches `name_pattern` (case-insensitive substring or glob),
    optionally grep'ing their content for `content_query`.
    """
    name_pattern = (name_pattern or "").strip().lower()
    content_query = (content_query or "").strip()
    if not name_pattern and not content_query:
        return "Provide a name_pattern (e.g. 'resume', '*.pdf') or content_query."

    # Compile name matcher — support either a glob or a substring.
    has_glob = any(ch in name_pattern for ch in "*?[")

    def name_matches(name: str) -> bool:
        if not name_pattern:
            return True
        low = name.lower()
        if has_glob:
            from fnmatch import fnmatch
            return fnmatch(low, name_pattern)
        return name_pattern in low

    grep_re = re.compile(re.escape(content_query), re.IGNORECASE) if content_query else None

    scanned = 0
    hits: list[tuple[Path, str]] = []
    for root in _scope_dirs():
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                scanned += 1
                if scanned > MAX_FILES_SCANNED:
                    break
                if not name_matches(fn):
                    continue
                p = Path(dirpath) / fn
                snippet = ""
                if grep_re:
                    try:
                        size = p.stat().st_size
                        if size > MAX_BYTES_PER_FILE_FOR_GREP:
                            continue
                        text = p.read_text(encoding="utf-8", errors="replace")
                        m = grep_re.search(text)
                        if not m:
                            continue
                        # Build a small snippet around the match
                        start = max(0, m.start() - 40)
                        end = min(len(text), m.end() + 40)
                        snippet = "..." + text[start:end].replace("\n", " ") + "..."
                    except Exception:
                        continue
                hits.append((p, snippet))
                if len(hits) >= max_results:
                    break
            if len(hits) >= max_results or scanned > MAX_FILES_SCANNED:
                break

    if not hits:
        return f"No files found for name_pattern='{name_pattern}'" + (f" + content='{content_query}'." if content_query else ".")

    lines = []
    for path, snippet in hits:
        line = f"- {path}"
        if snippet:
            line += f"\n    {snippet}"
        lines.append(line)
    return f"Found {len(hits)} result(s):\n" + "\n".join(lines)
