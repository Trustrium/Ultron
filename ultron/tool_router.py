"""Dynamic tool routing — send only the relevant tools to the LLM per query.

Why: with 100+ tools, sending every schema on every call wastes thousands of
tokens (slower + burns quota). The router combines two signals:

  1. Multilingual synonyms (ultron/tool_synonyms.py) — exact-phrase matches
     in English / Hindi / Urdu / Roman Urdu / Roman Hindi. This is the ONLY
     thing that works for non-English phrasings, because tool descriptions
     are English and BM25 cannot match "कैमरा खोलो" to "open_app" on its own.
  2. BM25 over each tool's name + description for everything else.

Low-confidence fallback: when the best BM25 score is low (typical for
non-English queries, where no description token matches), the router returns
a BROADER set — CORE + synonym tools + top-k BM25 even at score 0 — instead
of a possibly-empty or wrong narrow set. Optionally, if an LLM client is
passed, it asks the LLM to pick the tools (one extra call; NOT used on the
hot path by default because it adds latency).

The router NEVER dispatches anything: it only chooses which tool schemas
the LLM sees. The LLM always makes the final tool choice.
"""
from __future__ import annotations

from .tool_synonyms import normalize_query

# Tokenizer: split on Unicode punctuation / symbols / controls via the same
# normalizer the synonym map uses, so Devanagari combining marks (which \w
# does NOT match) survive instead of shredding Hindi tokens. The old pattern
# [A-Za-z0-9_]+ silently dropped every Devanagari / Urdu-script token.

# Always available regardless of query — cheap, broadly useful, or meta.
CORE_TOOLS = {
    "current_time", "remember", "recall", "recall_similar", "list_reminders",
    "add_reminder", "open_app", "web_search_real", "accomplish", "auto_pilot",
    "stop_autopilot", "daily_briefing", "set_personality",
}

DEFAULT_K = 25

# BM25 top score at or below this counts as "low confidence" -> broader set.
# BM25 scores for short queries against short descriptions are small; 0.5 was
# chosen so that a single genuine token match (typically >= ~1.0) still counts
# as confident, while zero/near-zero matches fall back. See diagnose_routing().
LOW_SCORE_THRESHOLD = 0.5

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
    return [w.lower() for w in normalize_query(t).split() if w]


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


def _bm25_scores(query: str, all_tools: list[dict]) -> tuple[list[float], list[str]]:
    """Return (scores, names) aligned with all_tools, or ([], []) if BM25 unavailable."""
    sig = len(all_tools)
    if _cache["sig"] != sig:
        bm25, names = _build(all_tools)
        _cache.update(sig=sig, bm25=bm25, names=names)
    bm25, names = _cache["bm25"], _cache["names"]
    if bm25 is None or not names:
        return [], []
    q = _tokenize(query)
    if not q:
        return [0.0] * len(names), names
    return list(bm25.get_scores(q)), names


def llm_select_tools(query: str, all_tools: list[dict], client, k: int = DEFAULT_K) -> list[dict]:
    """Ask an LLM to pick the most relevant tool names for ``query``.

    Used ONLY as an explicit opt-in fallback (pass llm_client= to select_tools).
    Never on the hot path: it costs one extra LLM call. Any failure returns
    the broader deterministic set (CORE + top-k by BM25), never empty.
    """
    from .tool_synonyms import synonym_tool_names
    try:
        catalog = "\n".join(
            f"- {t['name']}: {t.get('description', '')[:160]}" for t in all_tools
        )
        prompt = (
            "Pick the tool names most relevant to this user request. "
            "Reply with ONLY a comma-separated list of tool names, no other text.\n\n"
            f"Request: {query}\n\nTools:\n{catalog}"
        )
        resp = client.chat(
            "You select tools for a voice assistant. Reply with only tool names.",
            [client.make_user_message(prompt)],
            [],
        )
        picked = {p.strip() for p in (resp.text or "").replace("\n", ",").split(",")}
        known = {t["name"] for t in all_tools}
        chosen = (picked & known) | CORE_TOOLS | synonym_tool_names(query)
        subset = [t for t in all_tools if t["name"] in chosen]
        return subset if len(subset) >= 5 else cap_tools(all_tools)
    except Exception as e:
        print(f"[router] llm_select_tools failed ({e}); using broader set.")
        return cap_tools(all_tools)


def diagnose_routing(query: str, all_tools: list[dict]) -> dict:
    """Debugging helper: show why a query routed the way it did."""
    from .tool_synonyms import synonym_tool_names
    scores, names = _bm25_scores(query, all_tools)
    top = max(scores) if scores else 0.0
    return {
        "query": query,
        "bm25_top_score": round(float(top), 3),
        "low_confidence": bool(top <= LOW_SCORE_THRESHOLD),
        "synonym_tools": sorted(synonym_tool_names(query)),
        "bm25_available": bool(scores),
    }


def select_tools(query: str, all_tools: list[dict], k: int = DEFAULT_K,
                 enabled: bool = True, llm_client=None) -> list[dict]:
    """Return a relevant subset of tools for the query.

    CORE + synonym tools + top-k by BM25. When BM25 confidence is low, the
    set is broadened (CORE + synonyms + top-k even at score 0) so the LLM
    still sees the right tool; with ``llm_client`` given, the LLM picks
    instead. Never returns an empty/tiny set.
    """
    if not enabled or not query or len(all_tools) <= k:
        return cap_tools(all_tools)

    from .tool_synonyms import synonym_tool_names
    synonym_tools = synonym_tool_names(query)

    if llm_client is not None:
        scores, _ = _bm25_scores(query, all_tools)
        top = max(scores) if scores else 0.0
        if top <= LOW_SCORE_THRESHOLD:
            return llm_select_tools(query, all_tools, llm_client, k=k)

    scores, names = _bm25_scores(query, all_tools)
    if not scores:
        # No BM25 (rank_bm25 missing): CORE + synonyms + capped full set.
        chosen = set(CORE_TOOLS) | synonym_tools
        subset = [t for t in all_tools if t["name"] in chosen]
        rest = [t for t in all_tools if t["name"] not in chosen]
        return cap_tools(subset + rest)

    ranked = sorted(zip(scores, names), key=lambda x: x[0], reverse=True)
    top_score = ranked[0][0] if ranked else 0.0
    if top_score <= LOW_SCORE_THRESHOLD:
        # Low confidence (typical for non-English queries): BROADER set —
        # CORE + synonyms + top-k BM25 even at score 0. Never empty.
        chosen = {name for _, name in ranked[:k]} | CORE_TOOLS | synonym_tools
    else:
        chosen = {name for score, name in ranked[:k] if score > 0} | CORE_TOOLS | synonym_tools

    subset = [t for t in all_tools if t["name"] in chosen]
    # Safety: never return an empty/tiny set.
    return subset if len(subset) >= 5 else cap_tools(all_tools)
