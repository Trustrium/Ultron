"""Email reply drafting — read a recent email's full body and draft a reply.

Does NOT send; returns the draft for the user to review (then they can ask to send).
"""
from __future__ import annotations
import base64

from ..llm import make_llm_client

_client = None


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    """Walk a Gmail message payload and pull the text/plain (or html-stripped) body."""
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    if mime == "text/plain" and body.get("data"):
        return _decode_part(body["data"])
    # Multipart — recurse
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    # Fallback: html part
    if mime == "text/html" and body.get("data"):
        import re
        return re.sub(r"<[^>]+>", " ", _decode_part(body["data"]))
    return ""


def draft_email_reply(query: str = "is:unread", instructions: str = "") -> str:
    """Find the most recent email matching `query`, read it, and draft a reply.

    `instructions` steers the tone/content (e.g. 'politely decline', 'say yes, suggest Friday').
    """
    try:
        from .gmail import _service
        svc = _service()
        resp = svc.users().messages().list(userId="me", maxResults=1, q=query).execute()
        msgs = resp.get("messages", [])
        if not msgs:
            return f"No email found matching '{query}'."
        full = svc.users().messages().get(userId="me", id=msgs[0]["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        sender = headers.get("From", "?")
        subject = headers.get("Subject", "(no subject)")
        body = _extract_body(full["payload"])[:6000]
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        return f"Could not read email: {e}"

    global _client
    if _client is None:
        _client = make_llm_client()
    prompt = (
        f"Draft a reply to this email. {('Instructions: ' + instructions) if instructions else ''}\n"
        f"Keep it appropriately concise and professional unless told otherwise. "
        f"Output ONLY the reply body (no subject line, no 'Dear', unless natural).\n\n"
        f"From: {sender}\nSubject: {subject}\n\n{body}"
    )
    try:
        r = _client.chat(
            system="You draft email replies in the user's voice — clear, courteous, to the point.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        draft = (r.text or "").strip()
    except Exception as e:
        return f"Draft generation failed: {e}"

    return (f"Reply draft for '{subject}' (from {sender}):\n\n{draft}\n\n"
            f"Say 'send it' to send this reply, or tell me what to change.")
