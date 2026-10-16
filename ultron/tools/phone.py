"""Phone calls + SMS via Twilio REST API (no SDK dependency — uses urllib + basic auth).

Setup (one time):
  - Sign up at https://www.twilio.com/try-twilio (free trial)
  - Get a Twilio phone number
  - Put in .env / Settings:
      TWILIO_SID=ACxxxx...
      TWILIO_TOKEN=your_auth_token
      TWILIO_FROM=+1234567890   (your Twilio number)

On the free trial you can only message/call VERIFIED numbers.
"""
from __future__ import annotations
import base64
import urllib.parse
import urllib.request

from ..config import TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM


def _configured() -> str:
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        return ("Phone isn't set up. Add TWILIO_SID, TWILIO_TOKEN and TWILIO_FROM in "
                "Settings/.env (free trial at twilio.com).")
    return ""


def _post(endpoint: str, fields: dict) -> dict:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/{endpoint}"
    data = urllib.parse.urlencode(fields).encode("utf-8")
    auth = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    import json
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_number(recipient: str) -> str:
    """Accept a raw number, or a contact name (looked up in contacts)."""
    r = (recipient or "").strip()
    if r.replace(" ", "").lstrip("+").isdigit():
        return r.replace(" ", "")
    # Try contacts by name
    try:
        from . import contacts as C
        for c in C._load():
            if r.lower() in c["name"].lower() and c.get("phone"):
                return c["phone"].replace(" ", "")
    except Exception:
        pass
    return r  # let Twilio validate


def send_sms(to: str, message: str) -> str:
    """Send an SMS. Confirm recipient + body with the user first."""
    err = _configured()
    if err:
        return err
    number = _resolve_number(to)
    if not message.strip():
        return "Message body is empty."
    try:
        res = _post("Messages.json", {"To": number, "From": TWILIO_FROM, "Body": message})
        sid = res.get("sid", "")
        return f"SMS sent to {to}." + (f" (id {sid[:10]})" if sid else "")
    except Exception as e:
        return f"SMS failed: {e}"


def make_call(to: str, message: str) -> str:
    """Place a call that speaks `message` aloud (Twilio TTS). Confirm first."""
    err = _configured()
    if err:
        return err
    number = _resolve_number(to)
    if not message.strip():
        return "Nothing to say on the call."
    twiml = f"<Response><Say voice=\"Polly.Brian\">{_escape(message)}</Say></Response>"
    try:
        res = _post("Calls.json", {"To": number, "From": TWILIO_FROM, "Twiml": twiml})
        sid = res.get("sid", "")
        return f"Calling {to} — Ultron will read your message." + (f" (id {sid[:10]})" if sid else "")
    except Exception as e:
        return f"Call failed: {e}"


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))
