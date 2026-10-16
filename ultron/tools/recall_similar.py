"""Semantic-ish recall over conversation log + notes + long-term memory.

Uses BM25 (rank_bm25 — pure Python, ~50 KB). Not as smart as embeddings,
but a massive upgrade over keyword grep, with zero heavyweight deps.

Indexes:
- data/conversation.log     (timestamped user + ultron turns)
- data/notes.md             (user notes)
- data/memory.json          (long-term facts)
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from ..config import CONVERSATION_LOG, MEMORY_FILE
from .notes import NOTES_FILE


_TOKEN_RE = re.compile(r"[A-Za-z0-9_'஀-௿]+")   # incl. Tamil unicode block


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _load_corpus() -> list[tuple[str, str]]:
    """Build (source_label, text) list from all three sources."""
    corpus: list[tuple[str, str]] = []

    # Conversation log — one entry per line, parse out the body
    if Path(CONVERSATION_LOG).exists():
        for line in Path(CONVERSATION_LOG).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: "YYYY-MM-DD HH:MM:SS ROLE[lang]: text"
            try:
                ts = line[:19]
                rest = line[19:].lstrip()
                role_part, _, body = rest.partition(":")
                role = role_part.split("[")[0].strip()
                if body.strip():
                    corpus.append((f"{ts} ({role})", body.strip()))
            except Exception:
                continue

    # Notes
    if NOTES_FILE.exists():
        for line in NOTES_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("-"):
                corpus.append(("note", line.lstrip("- ").strip()))

    # Long-term memory
    if Path(MEMORY_FILE).exists():
        try:
            data = json.loads(Path(MEMORY_FILE).read_text(encoding="utf-8"))
            for r in data:
                corpus.append((f"memory({r.get('key','?')})", str(r.get("value", ""))))
        except Exception:
            pass

    return corpus


def recall_similar(query: str, k: int = 5) -> str:
    """Return up to k most relevant past entries to the query."""
    query = (query or "").strip()
    if not query:
        return "Empty query."

    corpus = _load_corpus()
    if not corpus:
        return "No history yet — nothing to recall."

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return "rank_bm25 not installed. Run: pip install rank_bm25"

    tokenized = [_tokenize(t) for _, t in corpus]
    bm25 = BM25Okapi(tokenized)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return "Query has no searchable tokens."
    scores = bm25.get_scores(q_tokens)

    ranked = sorted(zip(scores, corpus), key=lambda x: x[0], reverse=True)
    hits = [(s, src, text) for s, (src, text) in ranked if s > 0][:max(1, int(k))]
    if not hits:
        return f"Nothing relevant found for '{query}'."

    lines = []
    for score, src, text in hits:
        snippet = text if len(text) <= 200 else text[:200] + "..."
        lines.append(f"- [{src}] (score {score:.1f}) {snippet}")
    return f"Top {len(hits)} relevant entries:\n" + "\n".join(lines)
