"""Language helpers for Ultron v3 — canonical language codes + script detection.

Canonical codes used across the app:
    "en"         -- English
    "roman_urdu" -- Urdu/Hindi written in Latin/Roman script (e.g. "camera kholo")
    "hindi"      -- Hindi in Devanagari script (e.g. "कैमरा खोलो")
    "urdu"       -- Urdu in Urdu (Arabic) script (e.g. "کیمرہ کھولو")
    "ta"         -- Tamil (legacy, still supported)

This module is stdlib-only (plus the tiny roman_urdu helper) so it can be
imported by tests and by listen.py without pulling in audio / Whisper deps.

IMPORTANT — spoken vs written language: Whisper returns a *spoken* language
code. Spoken Urdu is "urdu", NOT "roman_urdu" — "roman_urdu" only describes
Latin-script *written* text. Older code collapsed Whisper's "ur" into
"roman_urdu", which made the brain reply in Latin script even when the user
spoke/wrote real Urdu. That collapse is gone: hi -> hindi, ur -> urdu.
"""
from __future__ import annotations
import re

from .roman_urdu import detect_roman_urdu

# Whisper / BCP-47 style codes -> canonical Ultron codes.
_WHISPER_MAP = {
    "en": "en",
    "english": "en",
    "hi": "hindi",
    "hindi": "hindi",
    "hin": "hindi",
    "ur": "urdu",
    "urdu": "urdu",
    "urd": "urdu",
    "roman_urdu": "roman_urdu",
    "roman-urdu": "roman_urdu",
    "ta": "ta",
    "tamil": "ta",
    "tam": "ta",
}

# Per-language reply directive appended to the brain's system prompt so the
# model replies in the SAME language/script the user just used. Never force English.
LANGUAGE_DIRECTIVES = {
    "en": "Reply in English.",
    "roman_urdu": (
        "Reply in Roman Urdu — Urdu written in Latin/Roman script "
        "(e.g. 'Ho gaya, sir'). Do NOT use Devanagari or Arabic script."
    ),
    "hindi": (
        "Reply in Hindi using Devanagari script (e.g. 'हो गया, सर'). "
        "Do NOT reply in English or Roman Urdu."
    ),
    "urdu": (
        "Reply in Urdu using Urdu (Arabic) script (e.g. 'ہو گیا، سر'). "
        "Do NOT reply in English or Roman Urdu."
    ),
    "ta": "Reply in Tamil (Tamil script).",
}

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
# Arabic-block script. In this app's context Arabic-script input is treated as
# Urdu (the user's language); it is NOT assumed to be Arabic/Persian — those
# languages are not in Ultron's supported set, so "urdu" is the honest
# best-effort label for this block.
_ARABIC_BLOCK_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")


def normalize_language_code(code: str | None) -> str:
    """Map a Whisper / free-form language code to a canonical Ultron code."""
    if not code:
        return "en"
    key = str(code).strip().lower().replace("_", "-")
    if key in ("roman-urdu",):
        return "roman_urdu"
    return _WHISPER_MAP.get(key, key if key in ("en", "hindi", "urdu", "roman_urdu", "ta") else "en")


def detect_text_language(text: str) -> str:
    """Detect the language of *written* text from its script + vocabulary.

    Devanagari  -> hindi, Arabic-block -> urdu, Tamil block -> ta,
    Latin script with Roman-Urdu markers -> roman_urdu, else en.
    """
    if not text:
        return "en"
    if _DEVANAGARI_RE.search(text):
        return "hindi"
    if _ARABIC_BLOCK_RE.search(text):
        return "urdu"
    if _TAMIL_RE.search(text):
        return "ta"
    if detect_roman_urdu(text):
        return "roman_urdu"
    return "en"


def language_directive(lang: str) -> str:
    """System-prompt sentence forcing a reply in the user's language/script."""
    return LANGUAGE_DIRECTIVES.get((lang or "en").lower(), LANGUAGE_DIRECTIVES["en"])
