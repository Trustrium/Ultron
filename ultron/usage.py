"""Token usage tracking + rough cost estimates.

Persists daily totals to data/usage.json so the GUI can show "Today: X.Xk tokens (~$Y)".
"""
from __future__ import annotations
import datetime as _dt
import json
import threading
from pathlib import Path

from .config import DATA_DIR

USAGE_FILE = Path(DATA_DIR) / "usage.json"
_lock = threading.Lock()


# Approximate $ per 1M input/output tokens. Just for a "feel" — actual depends on model.
# (input_per_million, output_per_million)
PRICE_TABLE: dict[str, tuple[float, float]] = {
    # Groq — free tier billing-wise; we still estimate so user has a sense.
    "groq":         (0.0, 0.0),
    "ollama":       (0.0, 0.0),
    # OpenAI ballpark for GPT-4o mini
    "openai":       (0.15, 0.60),
    # Anthropic ballpark for Sonnet 4.x
    "anthropic":    (3.00, 15.00),
    # Gemini Flash
    "gemini":       (0.075, 0.30),
    # OpenRouter is variable; use a midline
    "openrouter":   (1.0, 4.0),
    "together":     (0.6, 0.9),
    "openai_compat":(0.0, 0.0),
}


def _today_key() -> str:
    return _dt.date.today().isoformat()


def _load() -> dict:
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[usage] save failed: {e}")


def record(provider: str, input_tokens: int, output_tokens: int) -> None:
    """Record one LLM call's token usage for today."""
    if input_tokens <= 0 and output_tokens <= 0:
        return
    with _lock:
        data = _load()
        day = _today_key()
        bucket = data.setdefault(day, {})
        slot = bucket.setdefault(provider or "unknown", {"calls": 0, "in": 0, "out": 0})
        slot["calls"] += 1
        slot["in"] += int(input_tokens)
        slot["out"] += int(output_tokens)
        _save(data)


def today_summary() -> dict:
    """Return aggregated counts + estimated cost for today, suitable for the status bar."""
    data = _load()
    day_data = data.get(_today_key(), {})
    total_in = 0
    total_out = 0
    total_calls = 0
    cost_usd = 0.0
    for provider, slot in day_data.items():
        total_in += slot.get("in", 0)
        total_out += slot.get("out", 0)
        total_calls += slot.get("calls", 0)
        prices = PRICE_TABLE.get(provider, (0.0, 0.0))
        cost_usd += (slot.get("in", 0) / 1_000_000) * prices[0]
        cost_usd += (slot.get("out", 0) / 1_000_000) * prices[1]
    return {
        "calls": total_calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "estimated_cost_usd": round(cost_usd, 4),
    }


def format_summary_short() -> str:
    s = today_summary()
    total = s["total_tokens"]
    if total == 0:
        return ""
    tokens_str = f"{total/1000:.1f}k" if total >= 1000 else str(total)
    cost = s["estimated_cost_usd"]
    cost_str = f" (~${cost:.2f})" if cost >= 0.01 else " (free)"
    return f"Today: {s['calls']} calls, {tokens_str} tokens{cost_str}"
