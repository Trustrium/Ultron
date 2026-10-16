"""Check GitHub for newer commits than the local repo.

Doesn't actually apply updates — just tells the user one is available and
shows the commit message + date. Updating is a `git pull` they run.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "Trustrium/Ultron"
BRANCH = "main"
API_URL = f"https://api.github.com/repos/{REPO}/branches/{BRANCH}"


def _local_head_sha() -> str | None:
    """Return the local repo's HEAD commit SHA, or None if not a git checkout."""
    try:
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["git", "-C", str(proj_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _remote_head_info() -> dict | None:
    """Hit GitHub API for the latest commit on main."""
    req = Request(API_URL, headers={"User-Agent": "Ultronupdater/1.0"})
    try:
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        commit = data.get("commit") or {}
        return {
            "sha": commit.get("sha"),
            "message": (commit.get("commit") or {}).get("message", ""),
            "date": ((commit.get("commit") or {}).get("author") or {}).get("date", ""),
            "html_url": commit.get("html_url", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def check_for_update() -> dict:
    """Return a dict with status: 'up_to_date' | 'update_available' | 'unknown' | 'error'."""
    local = _local_head_sha()
    remote = _remote_head_info()
    if remote is None or "error" in remote:
        return {"status": "error", "detail": (remote or {}).get("error", "no remote info")}
    if local is None:
        return {
            "status": "unknown",
            "detail": "Local copy is not a git checkout — can't compare. "
                      "Latest remote commit: " + remote.get("message", "")[:80],
            "remote": remote,
        }
    if local == remote.get("sha"):
        return {"status": "up_to_date", "local": local[:8], "remote": remote.get("sha", "")[:8]}
    return {
        "status": "update_available",
        "local": local[:8],
        "remote_sha": (remote.get("sha") or "")[:8],
        "commit_message": (remote.get("message") or "").split("\n", 1)[0],
        "commit_date": remote.get("date", ""),
        "url": remote.get("html_url", ""),
    }


def update_summary() -> str:
    """Short human-readable string for the GUI."""
    info = check_for_update()
    s = info.get("status")
    if s == "up_to_date":
        return f"✓ You're up to date (local={info.get('local')})."
    if s == "update_available":
        return (
            f"✨ Update available!\n"
            f"  Latest: {info.get('commit_message','')[:80]}\n"
            f"  Date: {info.get('commit_date','')[:10]}\n"
            f"  Run `git pull` in the project folder to update."
        )
    if s == "unknown":
        return f"⚠ {info.get('detail','')}"
    return f"⚠ Update check failed: {info.get('detail','')}"
