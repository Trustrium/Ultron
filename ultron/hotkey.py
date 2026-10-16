"""Global push-to-talk hotkey using the `keyboard` library.

Hotkey fires a callable on press. Lives in a daemon thread.
On Windows, `keyboard` works without admin for most key combos but may need
admin if the OS protects certain keys.
"""
from __future__ import annotations
from typing import Callable


class GlobalHotkey:
    def __init__(self, combo: str, callback: Callable[[], None]) -> None:
        self.combo = combo
        self.callback = callback
        self._handle = None
        self._active = False

    def start(self) -> bool:
        """Register the hotkey. Returns True on success, False on failure."""
        if self._active:
            return True
        try:
            import keyboard
        except Exception as e:
            print(f"[hotkey] 'keyboard' package not available: {e}")
            return False
        try:
            self._handle = keyboard.add_hotkey(self.combo, self._safe_call, suppress=False)
            self._active = True
            print(f"[hotkey] registered: {self.combo}")
            return True
        except Exception as e:
            print(f"[hotkey] failed to register '{self.combo}': {e}")
            return False

    def stop(self) -> None:
        if not self._active:
            return
        try:
            import keyboard
            if self._handle is not None:
                keyboard.remove_hotkey(self._handle)
        except Exception as e:
            print(f"[hotkey] stop: {e}")
        self._active = False
        self._handle = None

    def _safe_call(self):
        try:
            self.callback()
        except Exception as e:
            print(f"[hotkey] callback error: {e}")
