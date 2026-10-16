"""Quick voice-friendly notes — append to a markdown file with timestamps."""
import datetime as _dt
import threading

from ..config import DATA_DIR

NOTES_FILE = DATA_DIR / "notes.md"
_lock = threading.Lock()


def add_note(text: str, tag: str = "") -> str:
    text = (text or "").strip()
    if not text:
        return "Empty note — nothing saved."
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    tag_str = f" [{tag}]" if tag else ""
    line = f"- **{ts}**{tag_str}  {text}\n"
    with _lock:
        with NOTES_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    return f"Note saved: {text[:80]}"


def list_notes(max_results: int = 10, query: str = "") -> str:
    if not NOTES_FILE.exists():
        return "No notes yet."
    lines = NOTES_FILE.read_text(encoding="utf-8").splitlines()
    notes = [ln for ln in lines if ln.strip().startswith("- ")]
    if query:
        q = query.lower()
        notes = [n for n in notes if q in n.lower()]
    if not notes:
        return f"No notes match '{query}'." if query else "No notes yet."
    # Newest last (file is append-only); reverse so newest first when listing.
    notes = notes[::-1][:max_results]
    return "Recent notes:\n" + "\n".join(notes)


def clear_notes() -> str:
    if NOTES_FILE.exists():
        NOTES_FILE.unlink()
    return "All notes deleted."
