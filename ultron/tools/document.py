"""Document Q&A — read a local PDF / text file and answer questions about it.

Supports:
- .pdf  (via pypdf)
- .txt / .md / .csv / .py / .json / any UTF-8 text
"""
from __future__ import annotations
from pathlib import Path

from ..llm import make_llm_client

MAX_CHARS = 30_000   # cap what we feed the LLM (a few thousand tokens)
_client = None


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "(pypdf not installed — run: pip install pypdf)"
    try:
        reader = PdfReader(str(path))
        chunks = []
        for i, page in enumerate(reader.pages):
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
            if sum(len(c) for c in chunks) > MAX_CHARS:
                break
        return "\n\n".join(chunks)
    except Exception as e:
        return f"(PDF read error: {e})"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"(text read error: {e})"


def _read_any(path_str: str) -> tuple[str, str]:
    """Return (content_text, error_or_empty)."""
    p = Path(path_str).expanduser()
    if not p.exists():
        return "", f"File not found: {p}"
    if not p.is_file():
        return "", f"Not a file: {p}"
    if p.suffix.lower() == ".pdf":
        return _read_pdf(p), ""
    return _read_text(p), ""


def ask_document(path: str, question: str = "") -> str:
    """Read `path` and answer `question` about it. Empty question -> summarize."""
    content, err = _read_any(path)
    if err:
        return err
    if not content.strip():
        return f"{path} appears to be empty."

    global _client
    if _client is None:
        _client = make_llm_client()

    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n\n[...document truncated...]"

    prompt = (
        f"You will read a document and "
        + ("answer a question about it." if question else "summarize it briefly (3-5 sentences).")
        + "\n\n--- DOCUMENT ---\n" + content + "\n\n"
        + (f"--- QUESTION ---\n{question}\n" if question else "")
        + "Answer using ONLY the document. If the document does not contain the answer, say so."
    )
    try:
        resp = _client.chat(
            system="You answer questions about user-provided documents precisely.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        return (resp.text or "").strip() or "(empty answer)"
    except Exception as e:
        return f"Document Q&A failed: {e}"
