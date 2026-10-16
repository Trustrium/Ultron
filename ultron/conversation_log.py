"""Append-only log of user turns + Ultron replies. Useful for debugging and recall."""
import datetime as _dt
import threading

from .config import CONVERSATION_LOG

_log_lock = threading.Lock()


def log(role: str, text: str, lang: str = "") -> None:
    """Append one line to the conversation log."""
    if not text:
        return
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag = f"[{lang}]" if lang else ""
    line = f"{ts} {role.upper()}{tag}: {text}\n"
    try:
        with _log_lock:
            with CONVERSATION_LOG.open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        print(f"[conv-log] write failed: {e}")
