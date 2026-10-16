"""Personal profile — a structured, persistent picture of WHO the user is.

Distinct from free-form memory: this is organized into fields Ultron always
knows (name, location, work, family, preferences, goals, important dates).
Injected into every system prompt so replies feel personal.

Stored in data/profile.json.
"""
from __future__ import annotations
import json
import threading
from pathlib import Path

from ..config import DATA_DIR

PROFILE_FILE = Path(DATA_DIR) / "profile.json"
_lock = threading.Lock()

# Recognized profile fields (free-form values). 'family'/'preferences'/'goals'
# are lists; the rest are single strings.
FIELDS = {
    "name", "nickname", "location", "work", "role", "birthday",
    "languages", "family", "preferences", "goals", "important_dates", "notes",
}
LIST_FIELDS = {"family", "preferences", "goals", "important_dates"}


def _load() -> dict:
    if not PROFILE_FILE.exists():
        return {}
    try:
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    PROFILE_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def set_profile(field: str, value: str) -> str:
    """Set or append a profile field. List fields append; others overwrite."""
    field = (field or "").lower().strip().replace(" ", "_")
    value = (value or "").strip()
    if field not in FIELDS:
        return (f"Unknown profile field '{field}'. Known: {', '.join(sorted(FIELDS))}")
    if not value:
        return "Provide a value."
    with _lock:
        d = _load()
        if field in LIST_FIELDS:
            cur = d.get(field, [])
            if not isinstance(cur, list):
                cur = [cur]
            if value not in cur:
                cur.append(value)
            d[field] = cur
        else:
            d[field] = value
        _save(d)
    return f"Got it — your {field.replace('_', ' ')} is noted."


def get_profile() -> str:
    d = _load()
    if not d:
        return "I don't know much about you yet. Tell me about yourself and I'll remember."
    lines = ["Here's what I know about you:"]
    for k, v in d.items():
        label = k.replace("_", " ").capitalize()
        if isinstance(v, list):
            lines.append(f"  {label}: {', '.join(v)}")
        else:
            lines.append(f"  {label}: {v}")
    return "\n".join(lines)


def clear_profile_field(field: str) -> str:
    field = (field or "").lower().strip().replace(" ", "_")
    with _lock:
        d = _load()
        if field in d:
            del d[field]
            _save(d)
            return f"Cleared your {field.replace('_', ' ')}."
    return f"No '{field}' in your profile."


def profile_for_prompt(max_chars: int = 600) -> str:
    """Compact one-liner of the profile for injection into the system prompt."""
    d = _load()
    if not d:
        return ""
    parts = []
    for k, v in d.items():
        val = ", ".join(v) if isinstance(v, list) else v
        parts.append(f"{k.replace('_', ' ')}: {val}")
    text = "; ".join(parts)
    return text[:max_chars]
