"""Auto-start with Windows — toggle a registry Run entry.

Writes to: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
Value name: Ultron
"""
from __future__ import annotations
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Ultron"


def _current_run_command() -> str:
    """Best command to launch the app on boot.

    If running from PyInstaller bundle, sys.executable points at Ultron.exe.
    Otherwise we launch `python ultron_app.py --minimized` in the project dir.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    project = Path(__file__).resolve().parent.parent
    py = sys.executable
    return f'"{py}" "{project / "ultron_app.py"}" --minimized'


def is_enabled() -> bool:
    try:
        import winreg
    except Exception:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            try:
                winreg.QueryValueEx(k, APP_NAME)
                return True
            except FileNotFoundError:
                return False
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[autostart] read failed: {e}")
        return False


def enable() -> bool:
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _current_run_command())
        return True
    except Exception as e:
        print(f"[autostart] enable failed: {e}")
        return False


def disable() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass
        return True
    except Exception as e:
        print(f"[autostart] disable failed: {e}")
        return False


def sync_with(enabled: bool) -> bool:
    return enable() if enabled else disable()
