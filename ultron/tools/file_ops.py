"""File operations: move / copy / delete / rename / make-dir.

Every destructive op is reversible if it sends to the Recycle Bin (uses send2trash
if available, else permanent delete with explicit confirm flag).
"""
from __future__ import annotations
import shutil
from pathlib import Path

PROTECTED_DIRS = {
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\System Volume Information", "C:\\Users\\Default",
}


def _abs(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _is_protected(p: Path) -> bool:
    s = str(p)
    return any(s.startswith(prot) for prot in PROTECTED_DIRS)


def copy_file(src: str, dst: str) -> str:
    sp = _abs(src); dp = _abs(dst)
    if not sp.exists():
        return f"Source not found: {sp}"
    if _is_protected(dp):
        return f"Refusing to write to protected location: {dp}"
    try:
        dp.parent.mkdir(parents=True, exist_ok=True)
        if sp.is_dir():
            shutil.copytree(sp, dp, dirs_exist_ok=False)
        else:
            shutil.copy2(sp, dp)
        return f"Copied {sp} -> {dp}"
    except FileExistsError:
        return f"Destination exists: {dp}. Pick a different name."
    except Exception as e:
        return f"Copy failed: {e}"


def move_file(src: str, dst: str) -> str:
    sp = _abs(src); dp = _abs(dst)
    if not sp.exists():
        return f"Source not found: {sp}"
    if _is_protected(sp) or _is_protected(dp):
        return f"Refusing to touch protected location."
    try:
        dp.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sp), str(dp))
        return f"Moved {sp} -> {dp}"
    except Exception as e:
        return f"Move failed: {e}"


def rename_file(path: str, new_name: str) -> str:
    p = _abs(path)
    if not p.exists():
        return f"Path not found: {p}"
    target = p.parent / new_name
    try:
        p.rename(target)
        return f"Renamed to {target}"
    except Exception as e:
        return f"Rename failed: {e}"


def make_dir(path: str) -> str:
    p = _abs(path)
    if _is_protected(p):
        return f"Refusing to create inside protected location: {p}"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Directory ready: {p}"
    except Exception as e:
        return f"mkdir failed: {e}"


def delete_file(path: str, permanent: bool = False) -> str:
    """Delete a file. By default, sends to Recycle Bin (reversible)."""
    p = _abs(path)
    # Protected-location check FIRST — refuse regardless of whether it exists.
    if _is_protected(p):
        return f"Refusing to delete protected location: {p}"
    if not p.exists():
        return f"Path not found: {p}"
    if not permanent:
        try:
            from send2trash import send2trash
            send2trash(str(p))
            return f"Sent to Recycle Bin: {p}"
        except ImportError:
            return (f"send2trash not installed (run: pip install send2trash). "
                    f"Refusing permanent delete by default. Pass permanent=true if you really mean it.")
        except Exception as e:
            return f"Recycle-bin delete failed: {e}"
    # Permanent
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Permanently deleted {p}"
    except Exception as e:
        return f"Delete failed: {e}"
