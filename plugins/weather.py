"""Weather plugin — uses wttr.in (no API key required).

Adds:
- get_weather(location) -> current conditions + 3-day forecast.
"""
from __future__ import annotations
import urllib.request
import urllib.parse


def _wttr(location: str, fmt: str) -> str:
    location = (location or "").strip()
    if not location:
        return "Please provide a location (city, postcode, or 'auto' for IP-based)."
    if location.lower() == "auto":
        path = ""
    else:
        path = "/" + urllib.parse.quote(location)
    url = f"https://wttr.in{path}?format={urllib.parse.quote(fmt)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"Could not fetch weather: {e}"


try:
    from ultron.cache import ttl_cache
except Exception:
    def ttl_cache(seconds=120):
        def deco(fn):
            return fn
        return deco


@ttl_cache(seconds=600)
def get_weather_handler(args: dict) -> str:
    """Return current conditions + tomorrow + day-after, voice-friendly."""
    location = args.get("location", "auto")
    # Format string for wttr.in: %l = location, %C = condition, %t = temp, %h = humidity, %w = wind
    now = _wttr(location, "%l: %C %t, feels like %f, humidity %h, wind %w")
    if now.startswith("Could not"):
        return now
    # A short forecast: pull a 1-line summary for the next two days.
    try:
        forecast = _wttr(location, "%C %t (today) | %C %t (tomorrow)")
    except Exception:
        forecast = ""
    if forecast and not forecast.startswith("Could not"):
        return f"{now}.  Forecast: {forecast}"
    return now


TOOLS = [
    {
        "name": "get_weather",
        "description": (
            "Get current weather and a short forecast for a location. "
            "Use when user asks 'what's the weather', 'is it going to rain', "
            "or wants temperature info. Pass 'auto' to use IP-based location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, postcode, or 'auto' for IP-based location.",
                },
            },
        },
    },
]

HANDLERS = {
    "get_weather": get_weather_handler,
}
