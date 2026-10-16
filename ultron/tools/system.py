"""Basic PC controls: volume, lock, sleep, screenshot, time/date."""
import datetime as _dt
import os
import subprocess
from pathlib import Path

try:
    from ctypes import windll
except ImportError:
    windll = None


def _press_vk(vk_code: int, times: int = 1) -> None:
    """Simulate a keypress (Windows). VK codes: VOLUME_UP=0xAF, VOLUME_DOWN=0xAE, MUTE=0xAD."""
    import ctypes
    KEYEVENTF_KEYUP = 0x0002
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def volume_up(steps: int = 5) -> str:
    _press_vk(0xAF, steps)
    return f"Volume up {steps} steps."


def volume_down(steps: int = 5) -> str:
    _press_vk(0xAE, steps)
    return f"Volume down {steps} steps."


def mute_toggle() -> str:
    _press_vk(0xAD, 1)
    return "Toggled mute."


def lock_pc() -> str:
    if windll:
        windll.user32.LockWorkStation()
    return "PC locked."


def sleep_pc() -> str:
    subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
    return "Sleeping the PC."


def shutdown_pc(seconds: int = 30) -> str:
    subprocess.Popen(f"shutdown /s /t {seconds}", shell=True)
    return f"Shutting down in {seconds} seconds. Say 'cancel shutdown' to abort."


def cancel_shutdown() -> str:
    subprocess.Popen("shutdown /a", shell=True)
    return "Shutdown cancelled."


def _desktop_dir() -> Path:
    """Find the actual Desktop folder — works for OneDrive-synced users too."""
    candidates = [
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Desktop",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to home dir if neither exists.
    return Path.home()


def screenshot() -> str:
    """Save a screenshot to Desktop and return path."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Screenshot needs Pillow. Run: pip install pillow"
    try:
        img = ImageGrab.grab(all_screens=True)
    except TypeError:
        # Older Pillow doesn't support all_screens kwarg.
        img = ImageGrab.grab()
    out_dir = _desktop_dir()
    out = out_dir / f"screenshot_{_dt.datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        img.save(out)
        return f"Screenshot saved to {out}"
    except Exception as e:
        return f"Failed to save screenshot: {e}"


# ===== Media keys (Spotify, YouTube, any media player) =====

def media_play_pause() -> str:
    _press_vk(0xB3, 1)   # VK_MEDIA_PLAY_PAUSE
    return "Toggled play/pause."


def media_next() -> str:
    _press_vk(0xB0, 1)   # VK_MEDIA_NEXT_TRACK
    return "Next track."


def media_prev() -> str:
    _press_vk(0xB1, 1)   # VK_MEDIA_PREV_TRACK
    return "Previous track."


def media_stop() -> str:
    _press_vk(0xB2, 1)   # VK_MEDIA_STOP
    return "Stopped media."


def current_time() -> str:
    return _dt.datetime.now().strftime("%I:%M %p on %A, %d %B %Y")


def current_date() -> str:
    return _dt.datetime.now().strftime("%A, %d %B %Y")
