"""Dynamic tool routing — send only the relevant tools to the LLM per query.

Why: with 100+ tools, sending every schema on every call wastes thousands of
tokens (slower + burns quota). The router uses BM25 over each tool's name +
description to pick the most relevant subset for the user's message, unioned
with a small always-on CORE set.

Falls back to ALL tools if rank_bm25 is unavailable or the query is empty.
"""
from __future__ import annotations
import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

# Always available regardless of query — cheap, broadly useful, or meta.
CORE_TOOLS = {
    "current_time", "remember", "recall", "recall_similar", "list_reminders",
    "add_reminder", "open_app", "web_search_real", "accomplish", "auto_pilot",
    "stop_autopilot", "daily_briefing", "set_personality",
}

DEFAULT_K = 25

# Max tools per request — auto-adapts to the configured provider (Groq/OpenAI cap
# at 128; Anthropic/Gemini allow far more). Falls back to a safe 120 if config
# can't be imported for any reason.
try:
    from .config import TOOL_LIMIT as MAX_TOOLS
except Exception:
    MAX_TOOLS = 120

# Cache the BM25 index keyed by the tool-set signature so we rebuild only when
# the tool list changes (e.g. a plugin loads).
_cache: dict = {"sig": None, "bm25": None, "names": None}


def _tokenize(t: str) -> list[str]:
    return [w.lower() for w in _TOKEN_RE.findall(t or "")]


def cap_tools(tools: list[dict], prefer: list[str] | None = None) -> list[dict]:
    """Trim a tool list to MAX_TOOLS, always keeping CORE + preferred names."""
    if len(tools) <= MAX_TOOLS:
        return tools
    pref = set(prefer or [])
    keep, rest = [], []
    for t in tools:
        (keep if (t["name"] in CORE_TOOLS or t["name"] in pref) else rest).append(t)
    return (keep + rest)[:MAX_TOOLS]


def _build(tools: list[dict]):
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return None, None
    docs, names = [], []
    for t in tools:
        text = f"{t.get('name','')} {t.get('name','').replace('_',' ')} {t.get('description','')}"
        docs.append(_tokenize(text))
        names.append(t["name"])
    return BM25Okapi(docs), names


def select_tools(query: str, all_tools: list[dict], k: int = DEFAULT_K,
                 enabled: bool = True) -> list[dict]:
    """Return a relevant subset of tools for the query (CORE + top-k by BM25)."""
    if not enabled or not query or len(all_tools) <= k:
        return cap_tools(all_tools)

    sig = len(all_tools)
    if _cache["sig"] != sig:
        bm25, names = _build(all_tools)
        _cache.update(sig=sig, bm25=bm25, names=names)
    bm25, names = _cache["bm25"], _cache["names"]
    if bm25 is None:
        return cap_tools(all_tools)

    q = _tokenize(query)
    if not q:
        return cap_tools(all_tools)

    scores = bm25.get_scores(q)
    ranked = sorted(zip(scores, names), key=lambda x: x[0], reverse=True)
    chosen = {name for score, name in ranked[:k] if score > 0}
    chosen |= CORE_TOOLS

    subset = [t for t in all_tools if t["name"] in chosen]
    # Safety: never return an empty/tiny set.
    return subset if len(subset) >= 5 else cap_tools(all_tools)
