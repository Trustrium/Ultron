"""Health log — track water, weight, mood, steps, medication.

Stored in data/health.json: [{type, value, note, date_iso}]
"""
from __future__ import annotations
import json
import threading
import datetime as _dt
from pathlib import Path

from ..config import DATA_DIR

HEALTH_FILE = Path(DATA_DIR) / "health.json"
_lock = threading.Lock()

KNOWN = {"water", "weight", "mood", "steps", "medication", "sleep"}


def _load() -> list[dict]:
    if not HEALTH_FILE.exists():
        return []
    try:
        return json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    HEALTH_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def log_health(metric: str, value: str = "", note: str = "") -> str:
    """Log a health metric. metric: water | weight | mood | steps | medication | sleep."""
    metric = (metric or "").lower().strip()
    if not metric:
        return "What should I log? (water, weight, mood, steps, medication, sleep)"
    item = {
        "type": metric, "value": str(value), "note": note,
        "date_iso": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    extra = f" = {value}" if value else ""
    return f"Logged {metric}{extra}" + (f" ({note})" if note else "")


def health_summary(period: str = "today") -> str:
    """Summarize health logs for today | week | all."""
    items = _load()
    if not items:
        return "No health logs yet."
    now = _dt.datetime.now()
    period = (period or "today").lower().strip()

    def keep(iso: str) -> bool:
        try:
            d = _dt.datetime.fromisoformat(iso)
        except Exception:
            return False
        if period == "today":
            return d.date() == now.date()
        if period == "week":
            return (now - d).days < 7
        return True

    rows = [r for r in items if keep(r.get("date_iso", ""))]
    if not rows:
        return f"No health logs for this {period}."

    # Water count, latest weight/mood, medication count
    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r)
    lines = [f"Health ({period}):"]
    for t, entries in by_type.items():
        if t == "water":
            lines.append(f"  water: {len(entries)} logged")
        elif t in ("weight", "mood", "sleep"):
            last = entries[-1]
            lines.append(f"  {t}: {last['value']}")
        elif t == "medication":
            lines.append(f"  medication: {len(entries)} taken")
        elif t == "steps":
            lines.append(f"  steps: {entries[-1]['value']}")
        else:
            lines.append(f"  {t}: {len(entries)} entries")
    return "\n".join(lines)
