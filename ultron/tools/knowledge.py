"""Knowledge base — index a folder of documents, answer questions across all of them.

Uses BM25 (no heavy ML deps) over chunked text from .txt/.md/.pdf/.csv files.
Index cached in memory per folder for the session.
"""
from __future__ import annotations
import re
from pathlib import Path

from ..llm import make_llm_client

_TOKEN_RE = re.compile(r"[A-Za-z0-9_'஀-௿]+")
_CHUNK_CHARS = 1200
_indexes: dict[str, dict] = {}     # folder -> {chunks:[(src,text)], bm25, tokenized}
_client = None


def _tokenize(t: str) -> list[str]:
    return [w.lower() for w in _TOKEN_RE.findall(t or "")]


def _read_file_text(p: Path) -> str:
    ext = p.suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages[:50])
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _chunk(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [text[i:i + _CHUNK_CHARS] for i in range(0, len(text), _CHUNK_CHARS)] if text else []


def index_folder(folder: str) -> str:
    """Build a BM25 index over supported files in a folder (recursive)."""
    p = Path(folder).expanduser()
    if not p.exists() or not p.is_dir():
        return f"Not a folder: {p}"
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return "rank_bm25 not installed (pip install rank_bm25)."

    chunks: list[tuple[str, str]] = []
    exts = {".txt", ".md", ".pdf", ".csv", ".log", ".py", ".json"}
    files = [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in exts]
    for f in files[:200]:
        text = _read_file_text(f)
        for ch in _chunk(text):
            chunks.append((f.name, ch))
    if not chunks:
        return f"No readable documents found in {p}."

    tokenized = [_tokenize(c) for _, c in chunks]
    bm25 = BM25Okapi(tokenized)
    _indexes[str(p)] = {"chunks": chunks, "bm25": bm25}
    return f"Indexed {len(files)} files into {len(chunks)} chunks from {p}. Now ask questions with ask_knowledge."


def ask_knowledge(folder: str, question: str, k: int = 5) -> str:
    """Answer a question using the indexed folder (auto-indexes if needed)."""
    p = str(Path(folder).expanduser())
    if p not in _indexes:
        msg = index_folder(folder)
        if p not in _indexes:
            return msg
    idx = _indexes[p]
    q_tokens = _tokenize(question)
    if not q_tokens:
        return "Ask a real question."
    scores = idx["bm25"].get_scores(q_tokens)
    ranked = sorted(zip(scores, idx["chunks"]), key=lambda x: x[0], reverse=True)
    top = [(src, text) for s, (src, text) in ranked if s > 0][:max(1, int(k))]
    if not top:
        return f"Nothing relevant to '{question}' in the indexed folder."

    context = "\n\n".join(f"[{src}] {text}" for src, text in top)
    global _client
    if _client is None:
        _client = make_llm_client()
    prompt = (
        f"Answer the question using ONLY these document excerpts. Cite the file names. "
        f"If the answer isn't present, say so.\n\n--- EXCERPTS ---\n{context}\n\n"
        f"--- QUESTION ---\n{question}"
    )
    try:
        r = _client.chat(
            system="You answer questions strictly from provided document excerpts.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        return (r.text or "").strip() or "(no answer)"
    except Exception as e:
        return f"Knowledge answer failed: {e}"
