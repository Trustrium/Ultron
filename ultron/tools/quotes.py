"""Quick lookups: stock quotes (Yahoo Finance) + cricket scores (cricbuzz alternative).

All free, no API key. Best-effort scraping / public JSON endpoints.
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
from html import unescape

USER_AGENT = "Mozilla/5.0 Ultronquotes/7.0"


def _http(url: str, timeout: int = 8) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _stooq_symbol(sym: str) -> str:
    """Map common ticker formats to Stooq conventions.
    US tickers need '.US' suffix on stooq. Yahoo's '.NS' for NSE works as-is.
    """
    s = sym.lower()
    if "." in s:
        return s          # already qualified (e.g. tcs.ns, infy.ns)
    return s + ".us"      # bare ticker -> assume US


from ..cache import ttl_cache


@ttl_cache(seconds=120)
def stock_quote(symbol: str) -> str:
    """Get current price + day change. Symbol examples: AAPL, MSFT, TCS.NS, INFY.NS.

    Primary: Stooq (no auth). Fallback: Yahoo Finance chart endpoint (still works
    without the auth that v7/finance/quote now requires).
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return "Provide a stock symbol (e.g. AAPL, TCS.NS)."

    # --- Stooq CSV (no auth) ---
    try:
        stooq = _stooq_symbol(sym)
        url = (f"https://stooq.com/q/l/?s={urllib.parse.quote(stooq)}"
               f"&f=sd2t2ohlcv&h&e=csv")
        raw = _http(url).decode("utf-8", errors="replace").strip()
        lines = raw.splitlines()
        if len(lines) >= 2 and not lines[1].startswith("N/D"):
            # CSV: Symbol,Date,Time,Open,High,Low,Close,Volume
            fields = lines[1].split(",")
            if len(fields) >= 7:
                _sym, _date, _time, _open, _high, _low, close = fields[:7]
                try:
                    close_f = float(close)
                    open_f = float(_open)
                    change = close_f - open_f
                    pct = (change / open_f * 100.0) if open_f else 0.0
                    arrow = "UP" if change >= 0 else "DN"
                    return (f"{sym}: {close_f:.2f}  {arrow} {abs(change):.2f} "
                            f"({pct:+.2f}%)  [{_date} {_time}]")
                except ValueError:
                    pass
    except Exception:
        pass

    # --- Yahoo chart endpoint (no auth needed) ---
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
        data = json.loads(_http(url).decode("utf-8"))
        results = (data.get("chart") or {}).get("result") or []
        if not results:
            return f"No quote found for {sym}."
        meta = results[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        ccy = meta.get("currency", "")
        if price is None:
            return f"No price for {sym}."
        change = (price - prev) if prev else 0.0
        pct = (change / prev * 100.0) if prev else 0.0
        arrow = "UP" if change >= 0 else "DN"
        return (f"{sym}: {ccy} {price:.2f}  {arrow} {abs(change):.2f} ({pct:+.2f}%)")
    except Exception as e:
        return f"Stock quote failed: {e}"


def cricket_score(query: str = "") -> str:
    """Live cricket scores/fixtures from cricbuzz. With no query -> current matches.

    Parses the per-match anchor links (stable) whose title carries the teams,
    match number and status (Live / Preview / Complete / Upcoming).
    """
    try:
        html = _http("https://www.cricbuzz.com/cricket-match/live-scores").decode(
            "utf-8", errors="replace"
        )
    except Exception as e:
        return f"Cricket fetch failed: {e}"

    # <a href="/live-cricket-scores/<id>/..." title="Team vs Team, Nth Match - Status">
    links = re.findall(
        r'<a[^>]+href="/live-cricket-scores/(\d+)/[^"]+"[^>]*title="([^"]+)"', html
    )
    seen: set[str] = set()
    matches: list[str] = []
    for mid, title in links:
        if mid in seen:
            continue
        seen.add(mid)
        matches.append(unescape(title.strip()))

    if not matches:
        return "Couldn't reach cricbuzz right now (page format may have changed)."

    q = (query or "").strip().lower()
    if q:
        hits = [m for m in matches if q in m.lower()]
        if not hits:
            return f"No matches found for '{query}'."
        return "Cricket:\n" + "\n".join(f"- {m}" for m in hits[:8])

    # No query: surface live games first, then a few others.
    live = [m for m in matches if m.lower().endswith("- live") or " - live" in m.lower()]
    rest = [m for m in matches if m not in live]
    ordered = (live + rest)[:8]
    header = "Live cricket:" if live else "Cricket fixtures:"
    return header + "\n" + "\n".join(f"- {m}" for m in ordered)
