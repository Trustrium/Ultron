"""Gmail read + send via Google's Gmail API.

One-time setup (see README section "Gmail setup"):
1. Enable Gmail API in Google Cloud Console for your project.
2. Create OAuth 2.0 Client ID (Desktop app type).
3. Download credentials.json into data/gmail_credentials.json
4. On first use, a browser opens for you to grant access; a token is cached.
"""
import base64
import os.path
from email.mime.text import MIMEText
from pathlib import Path

from ..config import DATA_DIR

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

CRED_FILE = DATA_DIR / "gmail_credentials.json"
TOKEN_FILE = DATA_DIR / "gmail_token.json"


def _service():
    """Build an authorized Gmail service. Runs OAuth flow first time."""
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
            "See README 'Gmail setup' for steps."
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
    return build("gmail", "v1", credentials=creds)


def list_inbox(max_results: int = 5) -> str:
    """Return a compact summary of the latest N inbox messages."""
    try:
        svc = _service()
        resp = svc.users().messages().list(userId="me", maxResults=max_results, q="in:inbox").execute()
        msgs = resp.get("messages", [])
        if not msgs:
            return "Inbox is empty."
        lines = []
        for m in msgs:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
            snippet = full.get("snippet", "")[:120]
            lines.append(
                f"• {headers.get('From','?')} — {headers.get('Subject','(no subject)')}\n  {snippet}"
            )
        return "Latest emails:\n" + "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail read failed: {e}"


def search_emails(query: str, max_results: int = 5) -> str:
    """Search Gmail with the query (e.g. 'from:amma', 'is:unread', 'subject:invoice')."""
    try:
        svc = _service()
        resp = svc.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
        msgs = resp.get("messages", [])
        if not msgs:
            return f"No emails found for: {query}"
        lines = []
        for m in msgs:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
            snippet = full.get("snippet", "")[:120]
            lines.append(
                f"• {headers.get('From','?')} — {headers.get('Subject','(no subject)')}\n  {snippet}"
            )
        return f"Search results for '{query}':\n" + "\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail search failed: {e}"


def send_email(to: str, subject: str, body: str) -> str:
    try:
        svc = _service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}."
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Gmail send failed: {e}"
