"""Maps — geocode places, distance + driving directions, open in browser map.

Free, no API key:
- Geocoding via OpenStreetMap Nominatim
- Routing via the public OSRM demo server
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
import webbrowser

from ..cache import ttl_cache

USER_AGENT = "Ultronmaps/18.0 (personal assistant)"


def _http(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


@ttl_cache(seconds=86400)
def _geocode(place: str):
    """Return (lat, lon, display_name) for a place name, or None."""
    place = (place or "").strip()
    if not place:
        return None
    url = ("https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
           + urllib.parse.quote(place))
    try:
        data = json.loads(_http(url).decode("utf-8"))
        if not data:
            return None
        d = data[0]
        return float(d["lat"]), float(d["lon"]), d.get("display_name", place)
    except Exception:
        return None


def _km(a, b) -> float:
    """Haversine fallback distance in km."""
    import math
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(h))


def distance(origin: str, destination: str) -> str:
    """Driving distance + time between two places (OSRM), with straight-line fallback."""
    a = _geocode(origin)
    b = _geocode(destination)
    if not a:
        return f"Couldn't find '{origin}'."
    if not b:
        return f"Couldn't find '{destination}'."
    # OSRM expects lon,lat
    url = (f"https://router.project-osrm.org/route/v1/driving/"
           f"{a[1]},{a[0]};{b[1]},{b[0]}?overview=false")
    try:
        data = json.loads(_http(url).decode("utf-8"))
        routes = data.get("routes") or []
        if routes:
            meters = routes[0]["distance"]
            secs = routes[0]["duration"]
            km = meters / 1000.0
            mins = secs / 60.0
            t = f"{mins/60:.1f} h" if mins >= 60 else f"{mins:.0f} min"
            return f"{origin} -> {destination}: {km:.1f} km by road, about {t} driving."
    except Exception:
        pass
    # Fallback: straight-line
    km = _km((a[0], a[1]), (b[0], b[1]))
    return f"{origin} -> {destination}: ~{km:.1f} km straight-line (road route unavailable)."


def directions(origin: str, destination: str) -> str:
    """Open turn-by-turn directions in the default browser (Google Maps)."""
    o = urllib.parse.quote(origin)
    d = urllib.parse.quote(destination)
    url = f"https://www.google.com/maps/dir/{o}/{d}"
    try:
        webbrowser.open(url)
        return f"Opened directions from {origin} to {destination} in your browser."
    except Exception as e:
        return f"Could not open directions: {e}"


def find_place(query: str) -> str:
    """Locate a place / address and report its coordinates + full name."""
    g = _geocode(query)
    if not g:
        return f"Couldn't find '{query}'."
    lat, lon, name = g
    return f"{name}\n  coordinates: {lat:.5f}, {lon:.5f}"
