"""Smart home via Home Assistant REST API.

Setup (one time):
  - In Home Assistant: profile -> Long-Lived Access Tokens -> create one.
  - Put it in .env (or Settings): HA_URL=http://<host>:8123  HA_TOKEN=<token>

Tools resolve devices by friendly name OR entity_id (e.g. "living room light"
matches light.living_room).
"""
from __future__ import annotations
import json
import urllib.request

from ..config import HA_URL, HA_TOKEN


def _configured() -> str:
    if not HA_URL or not HA_TOKEN:
        return ("Home Assistant isn't set up. Add HA_URL and HA_TOKEN in Settings/.env "
                "(create a Long-Lived Access Token in your HA profile).")
    return ""


def _req(method: str, path: str, body: dict | None = None):
    url = HA_URL.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _states() -> list[dict]:
    return _req("GET", "/api/states")


def _resolve(query: str, domain: str = "") -> str | None:
    """Find an entity_id by friendly name or id. Optional domain filter (light, switch...)."""
    q = (query or "").lower().strip()
    try:
        states = _states()
    except Exception:
        return None
    best = None
    for s in states:
        eid = s.get("entity_id", "")
        if domain and not eid.startswith(domain + "."):
            continue
        fn = (s.get("attributes", {}).get("friendly_name") or "").lower()
        if q == eid.lower() or q == fn:
            return eid
        if q and (q in fn or q in eid.lower()):
            best = best or eid
    return best


def list_devices(domain: str = "") -> str:
    err = _configured()
    if err:
        return err
    try:
        states = _states()
    except Exception as e:
        return f"Couldn't reach Home Assistant: {e}"
    rows = []
    for s in states:
        eid = s.get("entity_id", "")
        if domain and not eid.startswith(domain + "."):
            continue
        if eid.split(".")[0] in ("light", "switch", "climate", "fan", "media_player",
                                 "cover", "scene", "lock") or domain:
            fn = s.get("attributes", {}).get("friendly_name") or eid
            rows.append(f"  {fn} [{eid}] = {s.get('state')}")
    if not rows:
        return "No matching devices found."
    return "Devices:\n" + "\n".join(rows[:40])


def _call(domain: str, service: str, entity_id: str) -> str:
    _req("POST", f"/api/services/{domain}/{service}", {"entity_id": entity_id})
    return entity_id


def turn_on(query: str) -> str:
    err = _configured()
    if err:
        return err
    eid = _resolve(query)
    if not eid:
        return f"No device matching '{query}'."
    try:
        domain = eid.split(".")[0]
        _call(domain, "turn_on", eid)
        return f"Turned on {query}."
    except Exception as e:
        return f"Failed to turn on '{query}': {e}"


def turn_off(query: str) -> str:
    err = _configured()
    if err:
        return err
    eid = _resolve(query)
    if not eid:
        return f"No device matching '{query}'."
    try:
        domain = eid.split(".")[0]
        _call(domain, "turn_off", eid)
        return f"Turned off {query}."
    except Exception as e:
        return f"Failed to turn off '{query}': {e}"


def set_brightness(query: str, percent: int) -> str:
    err = _configured()
    if err:
        return err
    eid = _resolve(query, domain="light")
    if not eid:
        return f"No light matching '{query}'."
    try:
        pct = max(0, min(int(percent), 100))
        _req("POST", "/api/services/light/turn_on",
             {"entity_id": eid, "brightness_pct": pct})
        return f"Set {query} to {pct}%."
    except Exception as e:
        return f"Failed to set brightness: {e}"


def device_state(query: str) -> str:
    err = _configured()
    if err:
        return err
    eid = _resolve(query)
    if not eid:
        return f"No device matching '{query}'."
    try:
        s = _req("GET", f"/api/states/{eid}")
        return f"{query}: {s.get('state')}"
    except Exception as e:
        return f"Failed to read state: {e}"


def activate_scene(query: str) -> str:
    err = _configured()
    if err:
        return err
    eid = _resolve(query, domain="scene")
    if not eid:
        return f"No scene matching '{query}'."
    try:
        _req("POST", "/api/services/scene/turn_on", {"entity_id": eid})
        return f"Activated scene '{query}'."
    except Exception as e:
        return f"Failed to activate scene: {e}"
