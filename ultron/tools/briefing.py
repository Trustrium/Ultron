"""Daily briefing — combines today's reminders + unread Gmail count + a friendly greeting."""
import datetime as _dt

from . import reminders as t_reminders


def _greeting() -> str:
    h = _dt.datetime.now().hour
    if h < 12:   return "Good morning"
    if h < 17:   return "Good afternoon"
    if h < 22:   return "Good evening"
    return "Good evening"


def daily_briefing(include_email: bool = True, max_email_results: int = 3) -> str:
    """Return a short, voice-friendly briefing of the user's day."""
    parts: list[str] = [f"{_greeting()}."]

    # Today's reminders
    today = t_reminders.reminders_due_today()
    if not today:
        parts.append("You have no reminders for today.")
    else:
        parts.append(f"You have {len(today)} reminder{'s' if len(today) != 1 else ''} today:")
        for r in today[:5]:
            due = _dt.datetime.fromisoformat(r["due_iso"])
            parts.append(f"At {due.strftime('%I:%M %p').lstrip('0')} — {r['text']}.")

    # Unread email count (best-effort, silent on failure)
    if include_email:
        try:
            from . import gmail as t_gmail
            unread = t_gmail.search_emails("is:unread", max_results=max_email_results)
            # search_emails returns a formatted string; we just embed the headline.
            if "No emails found" not in unread and "failed" not in unread.lower() and "credentials" not in unread.lower():
                parts.append("And in your inbox:")
                parts.append(unread)
        except Exception:
            pass

    return "  ".join(parts)
