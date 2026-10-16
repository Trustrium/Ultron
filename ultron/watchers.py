"""Real-time watchers — Ultron monitors things in the background and alerts you.

Watch types:
  stock   — alert when a symbol goes above/below a price
  folder  — alert when new files appear in a folder
  cpu/ram — alert when usage crosses a percentage threshold

Stored in data/watches.json. A WatchEngine thread evaluates every check_every
seconds and calls on_alert(text) when a watch trips. Stock/threshold watches are
one-shot (auto-disable after firing); folder watches keep running.
"""
from __future__ import annotations
import json
import threading
import uuid
from pathlib import Path
from typing import Callable

from .config import DATA_DIR

WATCHES_FILE = Path(DATA_DIR) / "watches.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not WATCHES_FILE.exists():
        return []
    try:
        return json.loads(WATCHES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    WATCHES_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ===== Tool API =====

def add_watch(kind: str, target: str = "", direction: str = "above",
              value: str = "") -> str:
    """Create a watch.
    kind=stock: target=SYMBOL, direction=above|below, value=price
    kind=folder: target=folder path
    kind=cpu|ram: direction=above|below, value=percent
    """
    kind = (kind or "").lower().strip()
    if kind not in ("stock", "folder", "cpu", "ram"):
        return "Watch kind must be stock | folder | cpu | ram."
    w = {"id": uuid.uuid4().hex[:6], "kind": kind, "target": target,
         "direction": (direction or "above").lower(), "value": str(value),
         "enabled": True, "state": ""}
    if kind == "folder":
        p = Path(target).expanduser()
        if not p.is_dir():
            return f"Not a folder: {target}"
        w["state"] = json.dumps(sorted(x.name for x in p.iterdir()))
    with _lock:
        items = _load()
        items.append(w)
        _save(items)
    desc = {
        "stock": f"{target} {direction} {value}",
        "folder": f"new files in {target}",
        "cpu": f"CPU {direction} {value}%",
        "ram": f"RAM {direction} {value}%",
    }[kind]
    return f"Watching: {desc} [{w['id']}]"


def list_watches() -> str:
    items = [w for w in _load() if w.get("enabled")]
    if not items:
        return "No active watches."
    lines = []
    for w in items:
        if w["kind"] == "folder":
            lines.append(f"  [{w['id']}] folder: {w['target']}")
        elif w["kind"] == "stock":
            lines.append(f"  [{w['id']}] {w['target']} {w['direction']} {w['value']}")
        else:
            lines.append(f"  [{w['id']}] {w['kind'].upper()} {w['direction']} {w['value']}%")
    return "Active watches:\n" + "\n".join(lines)


def delete_watch(watch_id: str) -> str:
    with _lock:
        items = _load()
        before = len(items)
        items = [w for w in items if w["id"] != watch_id]
        _save(items)
    return "Watch removed." if len(items) < before else f"No watch '{watch_id}'."


# ===== Engine =====

def _check(w: dict) -> str | None:
    """Return an alert string if the watch trips, else None. May mutate w['state']."""
    kind = w["kind"]
    try:
        if kind == "stock":
            from .tools.quotes import stock_quote
            q = stock_quote(w["target"])
            import re
            m = re.search(r"([\d,]+\.\d+)", q)
            if not m:
                return None
            price = float(m.group(1).replace(",", ""))
            thresh = float(w["value"])
            hit = price >= thresh if w["direction"] == "above" else price <= thresh
            if hit:
                return f"Stock alert: {w['target']} is {price:.2f} ({w['direction']} {thresh})."
        elif kind == "folder":
            p = Path(w["target"]).expanduser()
            if not p.is_dir():
                return None
            now = sorted(x.name for x in p.iterdir())
            prev = json.loads(w.get("state") or "[]")
            new = [n for n in now if n not in prev]
            w["state"] = json.dumps(now)
            if new:
                return f"New in {p.name}: {', '.join(new[:5])}"
        elif kind in ("cpu", "ram"):
            import psutil
            val = psutil.cpu_percent(interval=0.3) if kind == "cpu" else psutil.virtual_memory().percent
            thresh = float(w["value"])
            hit = val >= thresh if w["direction"] == "above" else val <= thresh
            if hit:
                return f"{kind.upper()} alert: {val:.0f}% ({w['direction']} {thresh}%)."
    except Exception:
        return None
    return None


class WatchEngine(threading.Thread):
    def __init__(self, on_alert: Callable[[str], None], check_every: float = 60.0):
        super().__init__(daemon=True)
        self.on_alert = on_alert
        self.check_every = check_every
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[watch] error: {e}")
            self._stop.wait(self.check_every)

    def _tick(self) -> None:
        with _lock:
            items = _load()
            changed = False
            for w in items:
                if not w.get("enabled"):
                    continue
                alert = _check(w)
                changed = True  # state may have updated (folder)
                if alert:
                    try:
                        self.on_alert(alert)
                    except Exception:
                        pass
                    # one-shot for stock/cpu/ram; folder keeps watching
                    if w["kind"] in ("stock", "cpu", "ram"):
                        w["enabled"] = False
            if changed:
                _save(items)

    def stop(self) -> None:
        self._stop.set()
