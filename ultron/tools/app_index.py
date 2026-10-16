r"""Discover and launch ANY installed app on Windows.

Sources (merged + cached to data/app_index.json):
  1. `Get-StartApps`  — every Start-menu app incl. Microsoft Store / UWP (Name + AppID)
  2. Start Menu .lnk shortcuts (system + user)
  3. PATH executables (fallback handled by apps.open_app)

Launch strategy per entry:
  - UWP / AppID  ->  explorer.exe shell:AppsFolder\<AppID>
  - .lnk path    ->  os.startfile(path)
"""
from __future__ import annotations
import difflib
import json
import os
import subprocess
import time
from pathlib import Path

from ..config import DATA_DIR

INDEX_FILE = Path(DATA_DIR) / "app_index.json"
INDEX_TTL_SECONDS = 24 * 3600   # rebuild at most once a day unless forced


def _get_start_apps() -> list[dict]:
    """All Start-menu apps (Win32 + UWP) via PowerShell. Returns [{name, appid}]."""
    ps = "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        )
        out = (result.stdout or "").strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        apps = []
        for item in data:
            name = (item.get("Name") or "").strip()
            appid = (item.get("AppID") or "").strip()
            if name and appid:
                apps.append({"name": name, "kind": "startapp", "target": appid})
        return apps
    except Exception as e:
        print(f"[app_index] Get-StartApps failed: {e}")
        return []


def _scan_start_menu() -> list[dict]:
    """Scan Start Menu .lnk shortcuts (system + user)."""
    dirs = []
    pd = os.environ.get("ProgramData")
    ad = os.environ.get("APPDATA")
    if pd:
        dirs.append(Path(pd) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if ad:
        dirs.append(Path(ad) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

    apps = []
    for d in dirs:
        if not d.exists():
            continue
        try:
            for lnk in d.rglob("*.lnk"):
                apps.append({"name": lnk.stem, "kind": "lnk", "target": str(lnk)})
        except Exception:
            continue
    return apps


def build_index(force: bool = False) -> dict:
    """Build (or load cached) app index. Returns {name_lower: {name, kind, target}}."""
    if not force and INDEX_FILE.exists():
        try:
            cached = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            if time.time() - cached.get("_built_at", 0) < INDEX_TTL_SECONDS:
                return cached.get("apps", {})
        except Exception:
            pass

    merged: dict[str, dict] = {}
    # Start Menu shortcuts first, then Start apps (so UWP AppIDs win for duplicates).
    for entry in _scan_start_menu() + _get_start_apps():
        key = entry["name"].lower().strip()
        if key:
            merged[key] = entry

    try:
        INDEX_FILE.write_text(
            json.dumps({"_built_at": time.time(), "apps": merged}, ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[app_index] cache write failed: {e}")

    return merged


def find_app(query: str) -> dict | None:
    """Fuzzy-match a spoken app name to the best installed app entry."""
    query = (query or "").strip().lower()
    if not query:
        return None
    apps = build_index()
    if not apps:
        return None

    names = list(apps.keys())

    # 1. Exact match
    if query in apps:
        return apps[query]

    # 2. Substring match — prefer the shortest name containing the query (most specific).
    substring_hits = [n for n in names if query in n]
    if substring_hits:
        best = min(substring_hits, key=len)
        return apps[best]

    # 3. Token overlap — query words all present in app name
    q_tokens = set(query.split())
    token_hits = [n for n in names if q_tokens.issubset(set(n.split()))]
    if token_hits:
        return apps[min(token_hits, key=len)]

    # 4. Fuzzy (difflib) as last resort
    close = difflib.get_close_matches(query, names, n=1, cutoff=0.6)
    if close:
        return apps[close[0]]

    return None


def launch_entry(entry: dict) -> str:
    kind = entry.get("kind")
    target = entry.get("target", "")
    name = entry.get("name", target)
    try:
        if kind == "startapp":
            # UWP / Store / modern app — launch via the AppsFolder shell namespace.
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{target}"])
            return f"Opened {name}."
        if kind == "lnk":
            os.startfile(target)
            return f"Opened {name}."
        # Unknown kind — try startfile
        os.startfile(target)
        return f"Opened {name}."
    except Exception as e:
        return f"Could not open {name}: {e}"


def open_installed_app(query: str) -> str | None:
    """Find + launch. Returns a result string, or None if no match found."""
    entry = find_app(query)
    if entry is None:
        return None
    return launch_entry(entry)


def list_apps(query: str = "", limit: int = 30) -> str:
    """List installed apps, optionally filtered by a substring query."""
    apps = build_index()
    if not apps:
        return "No apps discovered yet (index empty)."
    names = sorted({e["name"] for e in apps.values()})
    if query:
        q = query.lower()
        names = [n for n in names if q in n.lower()]
    if not names:
        return f"No installed apps match '{query}'."
    shown = names[:limit]
    more = f"\n...and {len(names) - limit} more" if len(names) > limit else ""
    return f"Installed apps ({len(names)}):\n" + "\n".join(f"- {n}" for n in shown) + more


def refresh_apps() -> str:
    apps = build_index(force=True)
    return f"Rebuilt app index — {len(apps)} apps discovered."
