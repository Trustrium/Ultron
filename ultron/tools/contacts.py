"""Contacts — a personal directory of people (name, phone, email, notes).

Stored in data/contacts.json: [{id, name, phone, email, notes, created_iso}]
"""
from __future__ import annotations
import json
import threading
import uuid
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

CONTACTS_FILE = Path(DATA_DIR) / "contacts.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not CONTACTS_FILE.exists():
        return []
    try:
        return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    CONTACTS_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def add_contact(name: str, phone: str = "", email: str = "", notes: str = "") -> str:
    name = (name or "").strip()
    if not name:
        return "A contact needs a name."
    with _lock:
        items = _load()
        # Update if the name already exists.
        for c in items:
            if c["name"].lower() == name.lower():
                if phone: c["phone"] = phone
                if email: c["email"] = email
                if notes: c["notes"] = notes
                _save(items)
                return f"Updated contact: {name}"
        items.append({
            "id": uuid.uuid4().hex[:6],
            "name": name, "phone": phone, "email": email, "notes": notes,
            "created_iso": _dt.datetime.now().isoformat(timespec="seconds"),
        })
        _save(items)
    return f"Contact saved: {name}" + (f" ({phone})" if phone else "")


def find_contact(query: str) -> str:
    q = (query or "").lower().strip()
    if not q:
        return "Who are you looking for?"
    items = _load()
    hits = [c for c in items if q in c["name"].lower()
            or q in (c.get("phone") or "") or q in (c.get("email") or "").lower()]
    if not hits:
        return f"No contact matching '{query}'."
    lines = []
    for c in hits[:10]:
        parts = [c["name"]]
        if c.get("phone"): parts.append(f"📞 {c['phone']}")
        if c.get("email"): parts.append(f"✉ {c['email']}")
        if c.get("notes"): parts.append(f"— {c['notes']}")
        lines.append("  " + "  ".join(parts))
    return "Found:\n" + "\n".join(lines)


def list_contacts() -> str:
    items = _load()
    if not items:
        return "No contacts saved yet."
    items.sort(key=lambda c: c["name"].lower())
    return "Contacts:\n" + "\n".join(f"  {c['name']}" + (f" — {c['phone']}" if c.get('phone') else "")
                                     for c in items[:50])


def delete_contact(name: str) -> str:
    n = (name or "").lower().strip()
    with _lock:
        items = _load()
        before = len(items)
        items = [c for c in items if c["name"].lower() != n]
        _save(items)
    return f"Deleted contact '{name}'." if len(items) < before else f"No contact named '{name}'."
