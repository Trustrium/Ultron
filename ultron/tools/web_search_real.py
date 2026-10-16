"""Real web search — scrape DuckDuckGo HTML (no API key, no rate limits in practice).

Returns titles + snippets + URLs of top results. Different from `web_search` which
just opens Google in a browser.
"""
from __future__ import annotations
import re
import urllib.parse
import urllib.request
from html import unescape

USER_AGENT = "Mozilla/5.0 Ultronsearch/7.0"


_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)


def _strip(s: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", s)).strip()


def web_search(query: str, max_results: int = 5) -> str:
    """Return top N results as a compact string."""
    query = (query or "").strip()
    if not query:
        return "Empty query."
    max_results = max(1, min(int(max_results or 5), 10))
    q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Search fetch failed: {e}"

    hits = _RESULT_RE.findall(html)[:max_results]
    if not hits:
        return f"No results found for: {query}"
    lines = [f"Top {len(hits)} results for '{query}':"]
    for i, (href, title, snippet) in enumerate(hits, 1):
        # DuckDuckGo wraps in a redirect: //duckduckgo.com/l/?uddg=ENCODED
        real_url = href
        if "uddg=" in href:
            try:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                real_url = urllib.parse.unquote(parsed.get("uddg", [""])[0])
            except Exception:
                pass
        lines.append(f"  {i}. {_strip(title)}")
        lines.append(f"     {real_url}")
        snip = _strip(snippet)
        if snip:
            lines.append(f"     {snip[:200]}")
    return "\n".join(lines)
