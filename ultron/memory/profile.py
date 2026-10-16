"""Persistent Ultron user profile — who sir is, what he likes, his projects.

Stored locally in data/ultron_profile.json (never committed, never sent anywhere).
Defaults are Rashid Ali / Trustrium; the user can change them in Settings.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _default_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "ultron_profile.json"


@dataclass
class UltronProfile:
    name: str = "Rashid Ali"
    address_as: str = "sir"
    languages: list[str] = field(default_factory=lambda: ["en", "roman_urdu"])
    company: str = "Trustrium"
    projects: list[str] = field(default_factory=lambda: [
        "MoboGravity", "Shadow Arena", "TIME & TIDE",
        "Echo Protocol", "Bulk Downloader", "Trustrium",
    ])
    preferences: dict = field(default_factory=lambda: {
        "reply_style": "short command -> execution -> brief report",
        "voice_replies": "1-2 sentences",
        "confirm_before_delete": True,
        "theme": "Ultron dark silver + orange-red",
    })
    goals: list[str] = field(default_factory=list)
    notes: str = ""


def load_profile(path: Path | None = None) -> UltronProfile:
    p = Path(path) if path else _default_path()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            # Only accept known fields
            known = {k: v for k, v in data.items() if k in UltronProfile.__dataclass_fields__}
            return UltronProfile(**known)
    except Exception:
        pass
    return UltronProfile()


def save_profile(profile: UltronProfile, path: Path | None = None) -> Path:
    p = Path(path) if path else _default_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def get_profile_summary(profile: UltronProfile | None = None) -> str:
    prof = profile or load_profile()
    projects = ", ".join(prof.projects) if prof.projects else "none yet"
    return (
        f"User: {prof.name} ({prof.company}), address as '{prof.address_as}'. "
        f"Languages: {', '.join(prof.languages)}. Projects: {projects}. "
        f"Style: {prof.preferences.get('reply_style', '')}"
    )
