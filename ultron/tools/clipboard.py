"""Windows clipboard read/write via pywin32. Falls back to a stdlib-only path on other OSes."""
from __future__ import annotations


def _win_read() -> str:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except TypeError:
            return ""
        return data or ""
    finally:
        win32clipboard.CloseClipboard()


def _win_write(text: str) -> None:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def read_clipboard() -> str:
    try:
        text = _win_read()
    except Exception as e:
        return f"Could not read clipboard: {e}"
    if not text.strip():
        return "Clipboard is empty."
    preview = text if len(text) < 800 else text[:800] + f"\n... (truncated, total {len(text)} chars)"
    return f"Clipboard contents:\n{preview}"


def write_clipboard(text: str) -> str:
    try:
        _win_write(text)
        return f"Copied to clipboard ({len(text)} chars)."
    except Exception as e:
        return f"Could not write clipboard: {e}"


def append_clipboard(text: str) -> str:
    current = ""
    try:
        current = _win_read()
    except Exception:
        pass
    new_text = (current + ("\n" if current else "") + text) if text else current
    try:
        _win_write(new_text)
        return f"Appended to clipboard ({len(text)} chars added)."
    except Exception as e:
        return f"Could not append: {e}"
