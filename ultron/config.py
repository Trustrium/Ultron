"""Central config — loads .env and exposes settings."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Windows consoles default to cp1252. On OUTPUT this crashes when printing tool
# results with unicode (e.g. ↗ in weather); on INPUT it mangles non-Latin text
# (e.g. typed Roman Urdu / Tamil) into broken surrogate chars that later fail to encode when
# sent to the LLM. Force UTF-8 on all three standard streams.
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Silence noisy HuggingFace warnings about anonymous downloads. Set BEFORE importing
# anything that pulls from HF Hub (faster-whisper does this lazily).
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


# ===== Ultron identity =====
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Ultron").strip() or "Ultron"
WAKE_WORD = os.getenv("WAKE_WORD", "Hey Ultron").strip() or "Hey Ultron"
# Languages: en + roman_urdu (Urdu written in Latin script). Legacy Tamil still accepted as "ta".
LANGUAGE = os.getenv("LANGUAGE", "en+roman_urdu").strip().lower() or "en+roman_urdu"


# ===== LLM provider config =====
# Pick one: groq | openai | anthropic | gemini | openrouter | ollama | together | openai_compat
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()

# Optional: a fallback LLM used automatically when the primary rate-limits / errors.
# Must be the SAME API family as the primary (e.g. primary=groq, fallback=gemini —
# both OpenAI-compatible). Great free pairing: Groq + Gemini.
LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower()
LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY", "").strip()
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "").strip()

# Optional: vision provider can differ from text provider.
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "").strip().lower()
VISION_API_KEY = os.getenv("VISION_API_KEY", "").strip()
VISION_MODEL = os.getenv("VISION_MODEL", "").strip()
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "").strip()


# ===== Backwards-compat: old GROQ_API_KEY / GROQ_MODEL etc still accepted =====
if not LLM_PROVIDER and (os.getenv("GROQ_API_KEY") or os.getenv("GROQ_MODEL")):
    LLM_PROVIDER = "groq"
    LLM_API_KEY = LLM_API_KEY or os.getenv("GROQ_API_KEY", "").strip()
    LLM_MODEL = LLM_MODEL or os.getenv("GROQ_MODEL", "").strip()
    VISION_MODEL = VISION_MODEL or os.getenv("GROQ_VISION_MODEL", "").strip()

# Final default — Groq (free, no card) with their free key if user just dropped one in.
if not LLM_PROVIDER:
    LLM_PROVIDER = "groq"
# Ultron default model for Groq free tier (overridden by LLM_MODEL / factory defaults).
if LLM_PROVIDER == "groq" and not LLM_MODEL:
    LLM_MODEL = "llama-3.3-70b-versatile"


# ===== Provider-aware tool-list cap =====
# Different providers cap how many tools you may send per request. Ultron adapts
# automatically to whatever API key the user configured — no manual setup. When a
# fallback is set, the SAME tool list is sent to whichever provider is active, so
# we use the strictest (smallest) limit of the configured providers.
_PROVIDER_TOOL_LIMITS = {
    "groq": 120,            # Groq hard-rejects > 128
    "openai": 120,          # OpenAI caps at 128
    "openai_compat": 120,   # unknown OpenAI-compatible endpoint — stay safe
    "openrouter": 120,
    "together": 120,
    "ollama": 120,
    "gemini": 120,          # Gemini function-calling also caps ~128
    "anthropic": 500,       # Claude handles hundreds of tools — expose them all
}


def _tool_limit_for(provider: str) -> int:
    return _PROVIDER_TOOL_LIMITS.get((provider or "").lower(), 120)


_active_providers = [LLM_PROVIDER] + ([LLM_FALLBACK_PROVIDER] if LLM_FALLBACK_PROVIDER else [])
TOOL_LIMIT = min(_tool_limit_for(p) for p in _active_providers)

# Optional manual override for power users (e.g. TOOL_LIMIT=173).
_tool_limit_override = os.getenv("TOOL_LIMIT", "").strip()
if _tool_limit_override.isdigit() and int(_tool_limit_override) > 0:
    TOOL_LIMIT = int(_tool_limit_override)


# ===== Fast-path LLM (v3 latency) =====
# Opt-in only (LLM_FAST_PATH=1). When enabled, Brain uses a small fast model
# (default: Groq llama-3.1-8b-instant) for the FIRST call of a turn ONLY when
# the request is a single-tool direct command detected reliably (synonym
# match, short, no conjunctions/questions, never destructive). If the fast
# call does not produce exactly one tool call, Brain discards it and retries
# with the main model — the fast path is speculative, never authoritative.
# Complex reasoning always stays on the main (70b) model.
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "llama-3.1-8b-instant").strip()
LLM_FAST_PATH = os.getenv("LLM_FAST_PATH", "").strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


# ===== Voice / wake config =====
TTS_VOICE_TAMIL = os.getenv("TTS_VOICE_TAMIL", "ta-IN-ValluvarNeural").strip()  # legacy, kept for compat
TTS_VOICE_ROMAN_URDU = os.getenv("TTS_VOICE_ROMAN_URDU", "en-IN-PrabhatNeural").strip()
TTS_VOICE_ENGLISH = os.getenv("TTS_VOICE_ENGLISH", "en-US-GuyNeural").strip()
TTS_VOICE_HINDI = os.getenv("TTS_VOICE_HINDI", "hi-IN-MadhurNeural").strip()
TTS_VOICE_URDU = os.getenv("TTS_VOICE_URDU", "ur-PK-AsadNeural").strip()
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny").strip()
MAX_LISTEN_SECONDS = int(os.getenv("MAX_LISTEN_SECONDS", "15"))
# Listen timings — tighter defaults for a snappier feel (v3 latency).
# LISTEN_SILENCE_SECONDS: silence that ends a recording (was hardcoded 0.8s).
# Keep >= 0.3s: below that, natural pauses cut the user off mid-sentence.
LISTEN_SILENCE_SECONDS = _env_float("LISTEN_SILENCE_SECONDS", 0.5)
LISTEN_MIN_SPEECH_SECONDS = _env_float("LISTEN_MIN_SPEECH_SECONDS", 0.5)
LISTEN_CALIBRATE_SECONDS = _env_float("LISTEN_CALIBRATE_SECONDS", 0.8)

# Home Assistant (smart home) — optional
HA_URL = os.getenv("HA_URL", "").strip()
HA_TOKEN = os.getenv("HA_TOKEN", "").strip()

# Twilio (phone calls + SMS) — optional
TWILIO_SID = os.getenv("TWILIO_SID", "").strip()
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "").strip()
TWILIO_FROM = os.getenv("TWILIO_FROM", "").strip()

# Telegram bridge (use Ultron from your phone) — optional
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
REMINDERS_FILE = DATA_DIR / "reminders.json"
MEMORY_FILE = DATA_DIR / "memory.json"
CONVERSATION_LOG = DATA_DIR / "conversation.log"
FOLLOWUP_SECONDS = int(os.getenv("FOLLOWUP_SECONDS", "8"))


def assert_keys():
    missing = []
    if not LLM_API_KEY:
        missing.append("LLM_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing required keys in .env: " + ", ".join(missing)
            + "\nCopy .env.example to .env and fill them in. See README.md."
        )
