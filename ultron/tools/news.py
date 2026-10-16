"""News briefing — pulls top headlines from free sources (no API keys).

Sources:
- Hacker News (top stories via Algolia API — no key)
- Google News RSS (topic-filtered)
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

USER_AGENT = "Mozilla/5.0 Ultronnews/6.0"


def _http(url: str, timeout: int = 8) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _hacker_news_top(limit: int = 5) -> list[dict]:
    try:
        url = (
            "https://hn.algolia.com/api/v1/search?"
            "tags=front_page&hitsPerPage=" + str(limit)
        )
        data = json.loads(_http(url).decode("utf-8"))
        out = []
        for hit in data.get("hits", [])[:limit]:
            out.append({
                "title": hit.get("title") or hit.get("story_title") or "(no title)",
                "url": hit.get("url") or hit.get("story_url") or "",
                "points": hit.get("points", 0),
            })
        return out
    except Exception as e:
        return [{"title": f"(HN fetch failed: {e})", "url": "", "points": 0}]


def _google_news(topic: str, limit: int = 5) -> list[dict]:
    """Topic-filtered Google News RSS — no API key needed."""
    try:
        q = urllib.parse.quote_plus(topic or "top stories")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        raw = _http(url)
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = _strip_html(item.findtext("description") or "")[:160]
            items.append({"title": title, "url": link, "description": desc})
        return items
    except Exception as e:
        return [{"title": f"(Google News fetch failed: {e})", "url": "", "description": ""}]


from ..cache import ttl_cache


@ttl_cache(seconds=300)
def news_briefing(topic: str = "", count: int = 5) -> str:
    """Return a short news briefing. If `topic` is given, focus on that; else mix HN + general."""
    count = max(1, min(int(count or 5), 10))
    if topic:
        items = _google_news(topic, limit=count)
        if not items:
            return f"No news found for: {topic}"
        lines = [f"News on '{topic}':"]
        for i, it in enumerate(items, 1):
            lines.append(f"  {i}. {it['title']}")
            if it.get("description"):
                lines.append(f"     {it['description']}")
        return "\n".join(lines)

    hn = _hacker_news_top(limit=count)
    gn = _google_news("top stories", limit=count)
    parts = []
    if hn:
        parts.append("Top on Hacker News:")
        for i, it in enumerate(hn, 1):
            parts.append(f"  {i}. {it['title']}  ({it.get('points', 0)} pts)")
    if gn:
        parts.append("\nTop world headlines:")
        for i, it in enumerate(gn, 1):
            parts.append(f"  {i}. {it['title']}")
    return "\n".join(parts) if parts else "Could not fetch news right now."
