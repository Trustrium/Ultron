"""Git operations on any local repo path — status, log, diff, branch, commit.

Commit is confirm-gated (destructive-ish). Never pushes automatically.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

MAX_OUT = 4000


def _run(args: list[str], cwd: str, timeout: int = 20) -> str:
    p = Path(cwd).expanduser()
    if not p.exists():
        return f"Path not found: {p}"
    try:
        result = subprocess.run(
            ["git", "-C", str(p)] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        out = (result.stdout or "") + (("\n[stderr] " + result.stderr) if result.stderr else "")
        out = out.strip()
        if len(out) > MAX_OUT:
            out = out[:MAX_OUT] + "\n...(truncated)"
        return out or f"(no output, exit={result.returncode})"
    except FileNotFoundError:
        return "git is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return "git command timed out."
    except Exception as e:
        return f"git error: {e}"


def git_status(repo: str = ".") -> str:
    return _run(["status", "--short", "--branch"], repo)


def git_log(repo: str = ".", n: int = 10) -> str:
    n = max(1, min(int(n), 50))
    return _run(["log", f"-{n}", "--oneline", "--decorate"], repo)


def git_diff(repo: str = ".", staged: bool = False) -> str:
    args = ["diff", "--stat"] + (["--staged"] if staged else [])
    return _run(args, repo)


def git_current_branch(repo: str = ".") -> str:
    return _run(["rev-parse", "--abbrev-ref", "HEAD"], repo)


def git_branches(repo: str = ".") -> str:
    return _run(["branch", "-a"], repo)


def git_commit(repo: str = ".", message: str = "", add_all: bool = True) -> str:
    """Stage (optionally) + commit. Confirm with user before calling. Does NOT push."""
    message = (message or "").strip()
    if not message:
        return "A commit needs a message."
    if add_all:
        add_res = _run(["add", "-A"], repo)
        if add_res.startswith(("Path not found", "git is not", "git error")):
            return add_res
    return _run(["commit", "-m", message], repo)
