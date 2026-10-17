"""Conversation-mode helpers — let Ultron hold a natural back-and-forth.

After the wake word triggers once, the voice loop stays in conversation: it keeps
listening + responding without needing "Hey Ultron" each turn, and ends gracefully
when the user signals they're done (or after repeated silence).

NOTE: is_exit_phrase() is a conversation-control convenience (end the
follow-up loop), NOT command dispatch. No tool is ever chosen by exact-string
matching — every request goes through Brain -> LLM -> tool_router.
"""
from __future__ import annotations
import re

# Phrases that end the conversation (English + Roman Urdu/Hindi + Hindi
# Devanagari + Urdu Arabic script + legacy Tamil/Tanglish).
_EXIT_PHRASES = {
    "that's all", "thats all", "that is all", "nothing else", "no thanks",
    "goodbye", "good bye", "bye", "bye bye", "stop", "exit", "quit",
    "thank you that's it", "we're done", "were done", "i'm done", "im done",
    "go to sleep", "sleep now", "dismiss",
    # Roman Urdu / Roman Hindi
    "bas", "bas karo", "khatam", "khatam karo", "ho gaya", "ruk jao",
    "khuda hafiz", "allah hafiz", "alvida", "phir milenge", "kafi hai",
    # Hindi (Devanagari)
    "बस", "बस करो", "खत्म", "खत्म करो", "हो गया", "रुक जाओ",
    "खुदा हाफ़िज़", "अलविदा", "फिर मिलेंगे", "काफ़ी है",
    # Urdu (Arabic script)
    "بس", "بس کرو", "ختم", "ختم کرو", "ہو گیا", "رک جاؤ",
    "خدا حافظ", "اللہ حافظ", "الوداع", "پھر ملیں گے", "کافی ہے",
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
    lang = (lang or "en").lower()
    if lang.startswith("ta"):
        return "சரி, தேவைப்படும்போது கூப்பிடுங்கள்."
    if lang == "hindi":
        return "ठीक है, जब ज़रूरत हो तो बुला लीजिएगा।"
    if lang == "urdu":
        return "ٹھیک ہے، جب ضرورت ہو تو بلا لیجیے گا۔"
    if lang == "roman_urdu":
        return "Theek hai — jab zaroorat ho to bula lijiyega."
    return "Alright — call me when you need me."
