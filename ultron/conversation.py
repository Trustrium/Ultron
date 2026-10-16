"""Conversation-mode helpers — let Ultron hold a natural back-and-forth.

After the wake word triggers once, the voice loop stays in conversation: it keeps
listening + responding without needing "Hey Ultron" each turn, and ends gracefully
when the user signals they're done (or after repeated silence).
"""
from __future__ import annotations
import re

# Phrases that end the conversation (English + common Tamil/Tanglish).
_EXIT_PHRASES = {
    "that's all", "thats all", "that is all", "nothing else", "no thanks",
    "goodbye", "good bye", "bye", "bye bye", "stop", "exit", "quit",
    "thank you that's it", "we're done", "were done", "i'm done", "im done",
    "go to sleep", "sleep now", "dismiss",
    # Tamil / Tanglish
    "podhum", "pothum", "sari podhum", "nandri", "vanakkam poitu varen", "poitu vaa",
}

_EXIT_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(p) for p in _EXIT_PHRASES) + r")[\s.!]*$",
    re.IGNORECASE,
)


def is_exit_phrase(text: str) -> bool:
    """True if the user clearly wants to end the conversation."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if _EXIT_RE.match(t):
        return True
    # Short utterances that are basically a goodbye
    if len(t) <= 18 and any(t == p or t.startswith(p + " ") for p in _EXIT_PHRASES):
        return True
    return False


def farewell(lang: str = "en") -> str:
    return "சரி, தேவைப்படும்போது கூப்பிடுங்கள்." if (lang or "").startswith("ta") \
        else "Alright — call me when you need me."
