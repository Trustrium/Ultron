"""Native OS notifications via plyer (Windows toast / macOS notification / Linux libnotify)."""
from __future__ import annotations


def toast(title: str, message: str, timeout: int = 8) -> bool:
    """Show a system notification. Returns True if it was dispatched."""
    try:
        from plyer import notification
    except Exception as e:
        print(f"[notify] plyer not available: {e}")
        return False
    try:
        notification.notify(
            title=title[:64] or "Ultron",
            message=message[:256] or "",
            app_name="Ultron",
            timeout=timeout,
        )
        return True
    except Exception as e:
        # plyer on Windows sometimes raises if WinRT is missing; degrade silently.
        print(f"[notify] toast failed: {e}")
        return False
