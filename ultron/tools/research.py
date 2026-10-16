"""Deep research agent — search the web, read the top results, synthesize a report.

Chains: web_search_real -> fetch_url (top N) -> LLM synthesis.
Optionally saves the report as a note.
"""
from __future__ import annotations

from ..llm import make_llm_client
from . import web_search_real as _search
from . import web_fetch as _fetch
from . import notes as _notes

_client = None


def research(topic: str, depth: int = 3, save_note: bool = False) -> str:
    """Research a topic by reading the top `depth` web results and synthesizing findings."""
    topic = (topic or "").strip()
    if not topic:
        return "Provide a topic to research."
    depth = max(1, min(int(depth or 3), 5))

    # 1. Search
    results_text = _search.web_search(topic, max_results=depth + 2)
    if results_text.startswith(("No results", "Search fetch failed", "Empty")):
        return f"Couldn't research '{topic}': {results_text}"

    # 2. Extract URLs from the search results block
    urls: list[str] = []
    for line in results_text.splitlines():
        line = line.strip()
        if line.startswith(("http://", "https://")):
            urls.append(line)
        if len(urls) >= depth:
            break

    # 3. Fetch + summarize each source
    sources: list[str] = []
    for i, url in enumerate(urls, 1):
        summary = _fetch.fetch_url(url, question=f"What does this say about: {topic}?")
        if summary and not summary.startswith(("Could not fetch", "LLM summary failed")):
            sources.append(f"[Source {i}] {url}\n{summary}")

    if not sources:
        return (f"Found search results for '{topic}' but couldn't extract readable content. "
                f"Here are the links:\n{results_text}")

    # 4. Synthesize
    global _client
    if _client is None:
        _client = make_llm_client()
    synthesis_prompt = (
        f"Synthesize a clear, well-organized briefing on the topic: \"{topic}\".\n"
        f"Base it ONLY on these sources. Note any disagreements. End with a 1-line takeaway.\n\n"
        + "\n\n".join(sources)
    )
    try:
        resp = _client.chat(
            system="You are a research analyst. Produce concise, accurate, well-structured briefings.",
            history=[_client.make_user_message(synthesis_prompt)],
            tools=[],
        )
        report = (resp.text or "").strip()
    except Exception as e:
        return f"Research synthesis failed: {e}\n\nRaw sources:\n" + "\n\n".join(sources)

    if not report:
        report = "Synthesis returned empty."

    out = f"Research: {topic}\n\n{report}\n\nSources:\n" + "\n".join(f"- {u}" for u in urls)

    if save_note:
        try:
            _notes.add_note(f"Research on '{topic}': {report[:500]}", tag="research")
            out += "\n\n(Saved to notes.)"
        except Exception:
            pass
    return out
