"""Voice presets — friendly names mapped to Edge TTS voices + rate/pitch tuning.

The Iron Man "J.A.R.V.I.S." preset uses British male Thomas with a slower rate
and slightly deeper pitch for that calm, sophisticated AI butler sound.
"""
from __future__ import annotations

# English presets — first one is the default Ultron voice.
ENGLISH_PRESETS: list[dict] = [
    {
        "id": "ultron",
        "label": "🤖 Ultron (British, mature, calm — default)",
        "voice": "en-GB-ThomasNeural",
        "rate": "-6%",
        "pitch": "-4Hz",
        "description": "Deep, calm, refined British — Ultron default voice.",
    },
    {
        "id": "ultron",
        "label": "🤖 Ultron (Iron Man — British, mature, calm)",
        "voice": "en-GB-ThomasNeural",
        "rate": "-6%",
        "pitch": "-4Hz",
        "description": "Deep, calm, refined British — closest to Marvel's J.A.R.V.I.S.",
    },
    {
        "id": "british_male_young",
        "label": "British male (younger, friendly)",
        "voice": "en-GB-RyanNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Bright, modern British accent.",
    },
    {
        "id": "british_female",
        "label": "British female (Sonia)",
        "voice": "en-GB-SoniaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Crisp British female voice.",
    },
    {
        "id": "american_male",
        "label": "American male (Guy)",
        "voice": "en-US-GuyNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Neutral American male.",
    },
    {
        "id": "american_female",
        "label": "American female (Aria)",
        "voice": "en-US-AriaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Warm American female.",
    },
    {
        "id": "indian_male",
        "label": "Indian English male (Prabhat)",
        "voice": "en-IN-PrabhatNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Indian English, male.",
    },
    {
        "id": "indian_female",
        "label": "Indian English female (Neerja)",
        "voice": "en-IN-NeerjaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Indian English, female.",
    },
    {
        "id": "deep_robotic",
        "label": "🎛  Deep robotic (slow, low pitch)",
        "voice": "en-US-AndrewNeural",
        "rate": "-10%",
        "pitch": "-5Hz",
        "description": "Slower, deeper — sci-fi AI feel.",
    },
]

TAMIL_PRESETS: list[dict] = [
    {
        "id": "tamil_male",
        "label": "Tamil male (Valluvar)",
        "voice": "ta-IN-ValluvarNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Tamil male voice.",
    },
    {
        "id": "tamil_female",
        "label": "Tamil female (Pallavi)",
        "voice": "ta-IN-PallaviNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Tamil female voice.",
    },
]


ROMAN_URDU_PRESETS: list[dict] = [
    {
        "id": "roman_urdu_male",
        "label": "Roman Urdu male (Prabhat — English voice, Urdu words)",
        "voice": "en-IN-PrabhatNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Speaks Roman Urdu text with an Indian-English voice.",
    },
    {
        "id": "roman_urdu_female",
        "label": "Roman Urdu female (Neerja — English voice, Urdu words)",
        "voice": "en-IN-NeerjaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Speaks Roman Urdu text with an Indian-English female voice.",
    },
]


# Hindi (Devanagari) — native hi-IN Edge voices.
HINDI_PRESETS: list[dict] = [
    {
        "id": "hindi_male",
        "label": "Hindi male (Madhur)",
        "voice": "hi-IN-MadhurNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Hindi male voice.",
    },
    {
        "id": "hindi_female",
        "label": "Hindi female (Swara)",
        "voice": "hi-IN-SwaraNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Hindi female voice.",
    },
]


# Urdu (Arabic script) — native ur-PK Edge voices.
URDU_PRESETS: list[dict] = [
    {
        "id": "urdu_male",
        "label": "Urdu male (Asad)",
        "voice": "ur-PK-AsadNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Urdu male voice.",
    },
    {
        "id": "urdu_female",
        "label": "Urdu female (Uzma)",
        "voice": "ur-PK-UzmaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "description": "Urdu female voice.",
    },
]


def roman_urdu_default() -> dict:
    return ROMAN_URDU_PRESETS[0]


def find_preset(presets: list[dict], voice_or_id: str) -> dict:
    """Match a stored voice id OR raw voice name to a preset. Returns first preset if no match."""
    voice_or_id = (voice_or_id or "").strip()
    for p in presets:
        if p["id"] == voice_or_id or p["voice"] == voice_or_id:
            return p
    return presets[0]


def english_default() -> dict:
    return ENGLISH_PRESETS[0]


def tamil_default() -> dict:
    return TAMIL_PRESETS[0]
