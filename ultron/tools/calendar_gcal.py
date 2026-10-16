"""Google Calendar — list events + add events. Shares the OAuth credentials file with Gmail.

Setup (one time, in your Google Cloud Console for the same project as Gmail):
  - APIs & Services -> Library -> 'Google Calendar API' -> Enable
  - The existing data/gmail_credentials.json is reused.
  - First call opens browser to grant the new 'calendar' scope.
"""
from __future__ import annotations
import datetime as _dt

from ..config import DATA_DIR

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

CRED_FILE = DATA_DIR / "gmail_credentials.json"
TOKEN_FILE = DATA_DIR / "google_token.json"   # separate from gmail_token.json since scopes differ


def _service():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Google API libs not installed. Run:\n"
            "  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    if not CRED_FILE.exists():
        raise RuntimeError(
            f"Place your OAuth client credentials at {CRED_FILE}. "
            "See README 'Gmail setup' (same file is reused)."
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CRED_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


def _format_event(ev: dict) -> str:
    summary = ev.get("summary", "(no title)")
    start = ev.get("start", {})
    when = start.get("dateTime") or start.get("date") or ""
    location = ev.get("location", "")
    loc = f" @ {location}" if location else ""
    return f"• {when}  {summary}{loc}"


def _events_in_range(time_min_iso: str, time_max_iso: str, max_results: int = 20) -> str:
    try:
        svc = _service()
        resp = svc.events().list(
            calendarId="primary",
            timeMin=time_min_iso, timeMax=time_max_iso,
            singleEvents=True, orderBy="startTime",
            maxResults=max_results,
        ).execute()
        events = resp.get("items", [])
        if not events:
            return "No events in that range."
        return "Events:\n" + "\n".join(_format_event(e) for e in events)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar read failed: {e}"


def list_today_events() -> str:
    now = _dt.datetime.now().astimezone()
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return _events_in_range(now.isoformat(), end.isoformat())


def list_week_events() -> str:
    now = _dt.datetime.now().astimezone()
    end = now + _dt.timedelta(days=7)
    return _events_in_range(now.isoformat(), end.isoformat())


def add_event(summary: str, start_time: str, duration_minutes: int = 60,
              description: str = "", location: str = "") -> str:
    """Add an event. `start_time` accepts 'YYYY-MM-DD HH:MM' or ISO.
    Uses the system timezone.
    """
    try:
        svc = _service()
        # Parse start
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                start = _dt.datetime.strptime(start_time.strip(), fmt)
                break
            except ValueError:
                start = None
        if start is None:
            try:
                start = _dt.datetime.fromisoformat(start_time.strip())
            except Exception:
                return f"Could not parse start_time '{start_time}'. Use 'YYYY-MM-DD HH:MM'."
        end = start + _dt.timedelta(minutes=max(5, int(duration_minutes)))
        local_tz = _dt.datetime.now().astimezone().tzinfo
        body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start.replace(tzinfo=local_tz).isoformat()},
            "end": {"dateTime": end.replace(tzinfo=local_tz).isoformat()},
        }
        ev = svc.events().insert(calendarId="primary", body=body).execute()
        return f"Event added: {summary} at {start.strftime('%a %d %b %I:%M %p')} (id={ev.get('id','?')[:10]})"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Calendar add failed: {e}"
