"""Roman Urdu support for Ultron — Urdu written in Latin script.

Used for language detection in text mode and for mapping common Roman Urdu
commands to English intents for tool routing. The brain replies in the same
language the user used (see brain.py SYSTEM_PROMPT).
"""
from __future__ import annotations
import re

ROMAN_URDU_KEYWORDS = {
    "kya", "kaise", "kab", "kahan", "kyun", "kis", "kitna", "kaun", "kaisa",
    "mera", "meri", "mere", "tera", "teri", "tere", "mujhe", "tum", "tumhara",
    "aap", "apka", "hai", "hain", "tha", "thi", "hoga", "nahi", "nahin",
    "karo", "kar", "karna", "do", "de", "batao", "bata", "bataye",
    "kholo", "khol", "band", "chalao", "chala", "dekho", "dekh", "sunao",
    "likho", "likh", "bhejo", "bhej", "dhoondo", "dhoond", "ruk", "ruko",
    "shuru", "khatam", "acha", "accha", "shukriya", "meherbani", "zaroor",
    "abhi", "kal", "aaj", "phir", "bhi", "aur", "yeh", "woh", "ye", "wo",
    "mujh", "usko", "isko", "kisko", "kabhi", "hamesha", "thoda", "bohat",
    "bahut", "kitne", "kaise", "kahan", "idhar", "udhar", "saath", "liye",
    "chahiye", "sakta", "sakti", "raha", "rahi", "rahe", "gaya", "aaya",
    "jao", "aao", "batao", "samjhao", "dikhao", "sunao", "chalo", "theek",
}

COMMAND_PHRASES = {
    "kholo": "open",
    "khol do": "open",
    "band karo": "close",
    "band kar do": "close",
    "batao": "tell me",
    "bata do": "tell me",
    "dhoondo": "find / search",
    "dhoond do": "find / search",
    "bhejo": "send",
    "bhej do": "send",
    "likho": "write",
    "likh do": "write",
    "chalao": "run / play",
    "chala do": "run / play",
    "ruk jao": "stop",
    "ruk ja": "stop",
    "shuru karo": "start",
    "shuru kar do": "start",
    "dikhao": "show",
    "dikha do": "show",
    "sunao": "tell me / play",
    "suna do": "tell me",
    "samjhao": "explain",
    "samjha do": "explain",
    "kya hai": "what is",
    "kaisa hai": "how is",
    "kahan hai": "where is",
    "kab hai": "when is",
}

_CONFIRM_WORDS_RU = {"han", "haan", "ji han", "kar do", "theek hai", "theek", "zaroor", "bilkul"}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+", (text or "").lower())


def detect_roman_urdu(text: str) -> bool:
    """Return True if text looks like Roman Urdu (not plain English)."""
    if not text:
        return False
    low = text.lower()
    # Strong signal: a known multi-word phrase.
    for phrase in COMMAND_PHRASES:
        if phrase in low:
            return True
    words = _words(text)
    if not words:
        return False
    hits = sum(1 for w in words if w in ROMAN_URDU_KEYWORDS)
    # 2+ keyword hits, or 1 hit in a very short command, counts as Roman Urdu.
    if hits >= 2:
        return True
    if hits == 1 and len(words) <= 4:
        return True
    return False


def translate_command(text: str) -> str:
    """Replace known Roman Urdu command phrases with English equivalents."""
    out = (text or "").strip()
    low = out.lower()
    for phrase, eng in COMMAND_PHRASES.items():
        if phrase in low:
            # Replace first occurrence, preserving rest of the sentence.
            idx = low.find(phrase)
            out = out[:idx] + eng + out[idx + len(phrase):]
            low = out.lower()
    return out


def is_confirmation(text: str) -> bool:
    return (text or "").strip().lower() in _CONFIRM_WORDS_RU
