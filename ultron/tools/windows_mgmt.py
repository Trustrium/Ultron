"""Window management via pygetwindow — focus / minimize / maximize / close by title."""
from __future__ import annotations


def _gw():
    import pygetwindow as gw
    return gw


def _find(title_query: str):
    """Return the best-matching visible window for a title substring."""
    gw = _gw()
    q = (title_query or "").lower().strip()
    candidates = [w for w in gw.getAllWindows() if (w.title or "").strip()]
    if not q:
        return None, candidates
    exact = [w for w in candidates if q == (w.title or "").lower()]
    if exact:
        return exact[0], candidates
    subs = [w for w in candidates if q in (w.title or "").lower()]
    if subs:
        # Prefer the shortest title (most specific).
        return min(subs, key=lambda w: len(w.title)), candidates
    return None, candidates


def list_windows() -> str:
    gw = _gw()
    titles = sorted({(w.title or "").strip() for w in gw.getAllWindows() if (w.title or "").strip()})
    if not titles:
        return "No open windows found."
    return "Open windows:\n" + "\n".join(f"- {t}" for t in titles[:30])


def active_window() -> str:
    try:
        gw = _gw()
        w = gw.getActiveWindow()
        if w is None or not (w.title or "").strip():
            return "No active window detected."
        return f"Active window: {w.title}"
    except Exception as e:
        return f"Could not get active window: {e}"


def focus_window(title_query: str) -> str:
    try:
        w, _ = _find(title_query)
        if w is None:
            return f"No window matching '{title_query}'."
        if w.isMinimized:
            w.restore()
        w.activate()
        return f"Focused: {w.title}"
    except Exception as e:
        return f"Focus failed: {e}"


def minimize_window(title_query: str) -> str:
    try:
        w, _ = _find(title_query)
        if w is None:
            return f"No window matching '{title_query}'."
        w.minimize()
        return f"Minimized: {w.title}"
    except Exception as e:
        return f"Minimize failed: {e}"


def maximize_window(title_query: str) -> str:
    try:
        w, _ = _find(title_query)
        if w is None:
            return f"No window matching '{title_query}'."
        w.maximize()
        return f"Maximized: {w.title}"
    except Exception as e:
        return f"Maximize failed: {e}"


def close_window(title_query: str) -> str:
    try:
        w, _ = _find(title_query)
        if w is None:
            return f"No window matching '{title_query}'."
        title = w.title
        w.close()
        return f"Closed: {title}"
    except Exception as e:
        return f"Close failed: {e}"
