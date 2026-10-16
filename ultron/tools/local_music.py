"""Local music — find audio files in the user's Music folders and play them.

Plays via the OS default player (os.startfile). Pair with the existing media-key
tools (media_play_pause / media_next) for transport control.
"""
from __future__ import annotations
import os
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}


def _music_dirs() -> list[Path]:
    home = Path.home()
    out = []
    for name in ("Music", "OneDrive/Music", "Downloads"):
        p = home / name
        if p.exists():
            out.append(p)
    return out


def _all_tracks() -> list[Path]:
    tracks: list[Path] = []
    for d in _music_dirs():
        try:
            for f in d.rglob("*"):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                    tracks.append(f)
                if len(tracks) > 3000:
                    return tracks
        except Exception:
            continue
    return tracks


def play_music(query: str = "") -> str:
    """Play a song matching `query` (by filename). Empty query plays the first track found."""
    tracks = _all_tracks()
    if not tracks:
        return ("No music files found in your Music or Downloads folders. "
                "Tip: I can also open YouTube/Spotify with 'open spotify'.")
    q = (query or "").lower().strip()
    if q:
        matches = [t for t in tracks if q in t.stem.lower()]
        if not matches:
            return f"No song matching '{query}'. Found {len(tracks)} tracks total."
        target = matches[0]
    else:
        target = tracks[0]
    try:
        os.startfile(str(target))
        return f"Playing: {target.stem}"
    except Exception as e:
        return f"Could not play '{target.name}': {e}"


def list_music(query: str = "", limit: int = 20) -> str:
    tracks = _all_tracks()
    if not tracks:
        return "No music files found."
    names = sorted({t.stem for t in tracks})
    if query:
        q = query.lower()
        names = [n for n in names if q in n.lower()]
    if not names:
        return f"No songs matching '{query}'."
    shown = names[:limit]
    more = f"\n...and {len(names) - limit} more" if len(names) > limit else ""
    return f"Music ({len(names)} matches):\n" + "\n".join(f"  {n}" for n in shown) + more
