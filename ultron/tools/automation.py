"""Keyboard + mouse automation via pyautogui — let Ultron operate the screen.

These are powerful + potentially disruptive, so the brain is told to confirm
before using them. A global PyAutoGUI failsafe (slam mouse to a corner) aborts.
"""
from __future__ import annotations

_pyautogui = None


def _gui():
    global _pyautogui
    if _pyautogui is None:
        import pyautogui
        pyautogui.FAILSAFE = True       # move mouse to top-left corner to abort
        pyautogui.PAUSE = 0.05
        _pyautogui = pyautogui
    return _pyautogui


def type_text(text: str, interval: float = 0.01) -> str:
    """Type a string into whatever has keyboard focus."""
    if not text:
        return "Nothing to type."
    try:
        _gui().typewrite(text, interval=max(0.0, min(float(interval), 0.2)))
        return f"Typed {len(text)} characters."
    except Exception as e:
        return f"Type failed: {e}"


def press_keys(keys: str) -> str:
    """Press a key or hotkey combo. Examples: 'enter', 'ctrl+s', 'alt+tab', 'win+d'."""
    keys = (keys or "").strip().lower()
    if not keys:
        return "No keys given."
    try:
        if "+" in keys:
            combo = [k.strip() for k in keys.split("+") if k.strip()]
            _gui().hotkey(*combo)
            return f"Pressed {keys}."
        _gui().press(keys)
        return f"Pressed {keys}."
    except Exception as e:
        return f"Key press failed: {e}"


def mouse_click(x: int | None = None, y: int | None = None,
                button: str = "left", clicks: int = 1) -> str:
    """Click at (x,y) or at the current position if not given."""
    try:
        g = _gui()
        btn = button if button in ("left", "right", "middle") else "left"
        n = max(1, min(int(clicks), 3))
        if x is not None and y is not None:
            g.click(x=int(x), y=int(y), button=btn, clicks=n)
            return f"Clicked {btn} at ({x},{y}) x{n}."
        g.click(button=btn, clicks=n)
        return f"Clicked {btn} at current position x{n}."
    except Exception as e:
        return f"Click failed: {e}"


def move_mouse(x: int, y: int, duration: float = 0.2) -> str:
    try:
        _gui().moveTo(int(x), int(y), duration=max(0.0, min(float(duration), 2.0)))
        return f"Moved mouse to ({x},{y})."
    except Exception as e:
        return f"Move failed: {e}"


def scroll(amount: int = -500) -> str:
    """Scroll vertically. Negative = down, positive = up."""
    try:
        _gui().scroll(int(amount))
        return f"Scrolled {amount}."
    except Exception as e:
        return f"Scroll failed: {e}"


def screen_size() -> str:
    try:
        w, h = _gui().size()
        return f"Screen size: {w} x {h}"
    except Exception as e:
        return f"Could not get screen size: {e}"


def mouse_position() -> str:
    try:
        x, y = _gui().position()
        return f"Mouse at ({x}, {y})"
    except Exception as e:
        return f"Could not get mouse position: {e}"
