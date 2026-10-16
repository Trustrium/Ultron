"""Fetch + clean + summarize any web page.

Strips HTML to readable text, then asks the configured LLM to summarize.
Useful for: "what's on this page", "summarize this article", "what does Wikipedia say about X".
"""
from __future__ import annotations
import re
import urllib.request
import urllib.parse
from html.parser import HTMLParser

from ..llm import make_llm_client

MAX_BODY_CHARS = 12_000   # cap what we send to the LLM
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Ultron/6.0"

_BLOCK_TAGS = {"script", "style", "noscript", "header", "footer", "nav",
               "aside", "form", "iframe", "svg"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        s = data.strip()
        if s:
            self._chunks.append(s)

    def text(self) -> str:
        return re.sub(r"\s+\n", "\n", " ".join(self._chunks)).strip()


def _fetch(url: str, timeout: int = 12) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read(2_000_000)   # 2 MB cap
    if "html" not in ctype.lower() and "xml" not in ctype.lower():
        # Plain text / JSON
        return raw.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    try:
        parser.feed(raw.decode("utf-8", errors="replace"))
    except Exception as e:
        return f"(parse error: {e})"
    return parser.text()


_client = None


def _summarize(text: str, question: str) -> str:
    """Send extracted text + a question to the configured LLM."""
    global _client
    if _client is None:
        _client = make_llm_client()
    prompt = (
        f"Below is the cleaned text content of a web page. "
        f"{'Answer the user question briefly and accurately based ONLY on the page content. '
            'If the page does not contain the answer, say so honestly.' if question else 'Summarize it briefly (2-4 sentences).'}\n\n"
        f"--- PAGE TEXT ---\n{text[:MAX_BODY_CHARS]}\n\n"
        + (f"--- QUESTION ---\n{question}\n" if question else "")
    )
    try:
        resp = _client.chat(
            system="You read web pages and answer questions or summarize them precisely.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        return (resp.text or "").strip() or "(empty summary)"
    except Exception as e:
        return f"LLM summary failed: {e}"


def fetch_url(url: str, question: str = "") -> str:
    """Fetch the URL, clean it, and return a summary (or answer to `question`)."""
    if not url:
        return "Please provide a URL."
    try:
        text = _fetch(url)
    except Exception as e:
        return f"Could not fetch {url}: {e}"
    if not text.strip():
        return f"{url} had no readable text content."
    return _summarize(text, question)
