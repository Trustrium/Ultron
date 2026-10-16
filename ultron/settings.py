"""Settings store — JSON file in user's AppData. Persists user choices from the GUI.

Falls back to .env / defaults when settings.json is absent. Once a user changes
something via the GUI, it's written here and takes precedence.
"""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from typing import Any


def _settings_dir() -> Path:
    """%APPDATA%\\Ultron on Windows, ~/.config/ultron elsewhere.
    Falls back to the legacy Ultron folder if it already exists (migration)."""
    appdata = os.getenv("APPDATA")
    if appdata:
        ultron_dir = Path(appdata) / "Ultron"
        legacy_dir = Path(appdata) / "Ultron"
        d = ultron_dir if (ultron_dir.exists() or not legacy_dir.exists()) else legacy_dir
    else:
        ultron_dir = Path.home() / ".config" / "ultron"
        legacy_dir = Path.home() / ".config" / "ultron"
        d = ultron_dir if (ultron_dir.exists() or not legacy_dir.exists()) else legacy_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


SETTINGS_FILE = _settings_dir() / "settings.json"

_lock = threading.Lock()
_cache: dict | None = None

# Keys we manage (so we don't blow away unknown user-added keys).
SCHEMA: dict[str, Any] = {
    "assistant_name": "Ultron",
    "wake_word": "Hey Ultron",
    "language": "en+roman_urdu",
    "llm_provider": "groq",
    "llm_api_key": "",
    "llm_model": "",
    "llm_base_url": "",
    "llm_fallback_provider": "",
    "llm_fallback_api_key": "",
    "llm_fallback_model": "",
    "vision_provider": "",
    "vision_api_key": "",
    "vision_model": "",
    "vision_base_url": "",
    "tts_voice_tamil": "tamil_male",  # legacy, kept for compat
    "tts_voice_roman_urdu": "roman_urdu_male",
    "tts_voice_english": "ultron",      # Ultron preset by default
    "whisper_model": "tiny",
    "max_listen_seconds": 15,
    "followup_seconds": 8,
    "auto_start_on_boot": False,
    "default_mode": "wake",     # wake | voice | text
    "ptt_enabled": True,
    "ptt_hotkey": "ctrl+alt+j",
    "personality": "ultron",
    "proactive_lead_minutes": 10,
    "tool_routing": True,          # send only relevant tools per query (faster, cheaper)
    "proactive_insights": True,    # let Ultron surface helpful nudges on its own
}


def _load_disk() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load() -> dict:
    """Load settings into the cache. Returns the full merged dict."""
    global _cache
    with _lock:
        if _cache is None:
            disk = _load_disk()
            merged = dict(SCHEMA)
            merged.update({k: v for k, v in disk.items() if k in SCHEMA})
            _cache = merged
        return dict(_cache)


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def save(updates: dict) -> None:
    """Update one or more settings and persist to disk."""
    global _cache
    with _lock:
        current = _load_disk()
        for k, v in updates.items():
            if k in SCHEMA:
                current[k] = v
        SETTINGS_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
        _cache = None  # force reload next get()


def settings_path() -> Path:
    return SETTINGS_FILE


# ===== Provider helpers =====

PROVIDER_INFO = [
    {"id": "groq",         "label": "Groq (free, fast)",            "key_url": "https://console.groq.com/keys",                 "key_prefix": "gsk_"},
    {"id": "openai",       "label": "OpenAI (GPT-4o etc.)",         "key_url": "https://platform.openai.com/api-keys",          "key_prefix": "sk-"},
    {"id": "anthropic",    "label": "Anthropic Claude",             "key_url": "https://console.anthropic.com/",                "key_prefix": "sk-ant-"},
    {"id": "gemini",       "label": "Google Gemini (free tier)",    "key_url": "https://aistudio.google.com/app/apikey",        "key_prefix": "AIza"},
    {"id": "openrouter",   "label": "OpenRouter (many models)",     "key_url": "https://openrouter.ai/keys",                    "key_prefix": "sk-or-"},
    {"id": "ollama",       "label": "Ollama (local, no internet)",  "key_url": "https://ollama.com/download",                   "key_prefix": ""},
    {"id": "together",     "label": "Together AI",                  "key_url": "https://api.together.xyz/settings/api-keys",    "key_prefix": ""},
    {"id": "openai_compat","label": "Custom OpenAI-compatible",     "key_url": "",                                              "key_prefix": ""},
]


# Curated model catalog per provider — shown in the Settings dialog dropdown.
# Each entry: (model_id, friendly_label)
# The user can still type a custom model name in the editable combo box.
MODEL_CATALOG: dict[str, list[tuple[str, str]]] = {
    "groq": [
        ("llama-3.3-70b-versatile",                          "Llama 3.3 70B  —  smart, balanced (default)"),
        ("llama-3.1-8b-instant",                             "Llama 3.1 8B   —  fastest, less smart"),
        ("meta-llama/llama-4-scout-17b-16e-instruct",        "Llama 4 Scout  —  multimodal (vision)"),
        ("meta-llama/llama-4-maverick-17b-128e-instruct",    "Llama 4 Maverick — biggest"),
        ("mixtral-8x7b-32768",                               "Mixtral 8x7B   —  long context"),
        ("gemma2-9b-it",                                     "Gemma 2 9B"),
    ],
    "openai": [
        ("gpt-4o-mini",         "GPT-4o mini   —  cheap, fast (default)"),
        ("gpt-4o",              "GPT-4o        —  flagship, multimodal"),
        ("gpt-4-turbo",         "GPT-4 Turbo"),
        ("gpt-4.1",             "GPT-4.1"),
        ("gpt-5",               "GPT-5         —  newest"),
        ("o3-mini",             "o3-mini       —  reasoning"),
        ("o1-mini",             "o1-mini       —  reasoning"),
    ],
    "anthropic": [
        ("claude-haiku-4-5",    "Claude Haiku 4.5   —  fastest, cheap"),
        ("claude-sonnet-4-6",   "Claude Sonnet 4.6  —  balanced (default)"),
        ("claude-opus-4-7",     "Claude Opus 4.7    —  smartest"),
    ],
    "gemini": [
        ("gemini-2.5-flash",    "Gemini 2.5 Flash  —  fast, free (default)"),
        ("gemini-2.5-pro",      "Gemini 2.5 Pro    —  smartest"),
        ("gemini-2.0-flash",    "Gemini 2.0 Flash"),
        ("gemini-1.5-flash",    "Gemini 1.5 Flash"),
        ("gemini-1.5-pro",      "Gemini 1.5 Pro"),
    ],
    "openrouter": [
        ("anthropic/claude-sonnet-4",                        "Claude Sonnet 4  (via OpenRouter)"),
        ("anthropic/claude-opus-4",                          "Claude Opus 4"),
        ("openai/gpt-4o",                                    "GPT-4o"),
        ("openai/gpt-4o-mini",                               "GPT-4o mini"),
        ("google/gemini-2.5-pro",                            "Gemini 2.5 Pro"),
        ("meta-llama/llama-3.3-70b-instruct",                "Llama 3.3 70B"),
        ("meta-llama/llama-4-scout",                         "Llama 4 Scout"),
        ("mistralai/mistral-large",                          "Mistral Large"),
        ("deepseek/deepseek-r1",                             "DeepSeek R1 — reasoning"),
    ],
    "ollama": [
        ("llama3.3",            "Llama 3.3 (must be pulled: `ollama pull llama3.3`)"),
        ("llama3.1",            "Llama 3.1"),
        ("qwen2.5",             "Qwen 2.5"),
        ("mistral",             "Mistral 7B"),
        ("gemma2",              "Gemma 2"),
        ("phi3",                "Phi 3"),
        ("llava",               "LLaVA — vision"),
    ],
    "together": [
        ("meta-llama/Llama-3.3-70B-Instruct-Turbo",          "Llama 3.3 70B Turbo (default)"),
        ("Qwen/Qwen2.5-72B-Instruct-Turbo",                  "Qwen 2.5 72B Turbo"),
        ("mistralai/Mixtral-8x7B-Instruct-v0.1",             "Mixtral 8x7B"),
        ("meta-llama/Llama-Vision-Free",                     "Llama Vision (free)"),
    ],
    "openai_compat": [],   # generic — user types their own model
}


def get_models_for(provider: str) -> list[tuple[str, str]]:
    """Return curated models for a provider. For ollama, also try to fetch installed models."""
    base = list(MODEL_CATALOG.get(provider, []))
    if provider == "ollama":
        installed = _list_ollama_models()
        if installed:
            # Replace catalog with installed list — only show what they actually have.
            base = [(m, f"{m}  (installed)") for m in installed]
    return base


def _list_ollama_models() -> list[str]:
    """Best-effort: query a local Ollama daemon for installed models. Returns [] on failure."""
    try:
        import json as _json
        from urllib.request import urlopen
        with urlopen("http://localhost:11434/api/tags", timeout=1.5) as r:
            data = _json.loads(r.read().decode("utf-8"))
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def apply_to_environ() -> None:
    """Copy settings into os.environ so the existing config.py picks them up.

    Called early in app startup BEFORE ultron.config is imported.
    """
    s = load()
    mapping = {
        "ASSISTANT_NAME": s.get("assistant_name", "Ultron"),
        "WAKE_WORD": s.get("wake_word", "Hey Ultron"),
        "LANGUAGE": s.get("language", "en+roman_urdu"),
        "LLM_PROVIDER":    s.get("llm_provider", ""),
        "LLM_API_KEY":     s.get("llm_api_key", ""),
        "LLM_MODEL":       s.get("llm_model", ""),
        "LLM_BASE_URL":    s.get("llm_base_url", ""),
        "LLM_FALLBACK_PROVIDER": s.get("llm_fallback_provider", ""),
        "LLM_FALLBACK_API_KEY":  s.get("llm_fallback_api_key", ""),
        "LLM_FALLBACK_MODEL":    s.get("llm_fallback_model", ""),
        "VISION_PROVIDER": s.get("vision_provider", ""),
        "VISION_API_KEY":  s.get("vision_api_key", ""),
        "VISION_MODEL":    s.get("vision_model", ""),
        "VISION_BASE_URL": s.get("vision_base_url", ""),
        "TTS_VOICE_TAMIL": s.get("tts_voice_tamil", ""),
        "TTS_VOICE_ROMAN_URDU": s.get("tts_voice_roman_urdu", ""),
        "TTS_VOICE_ENGLISH": s.get("tts_voice_english", ""),
        "WHISPER_MODEL":   s.get("whisper_model", ""),
        "MAX_LISTEN_SECONDS": str(s.get("max_listen_seconds", 15)),
        "FOLLOWUP_SECONDS":   str(s.get("followup_seconds", 8)),
    }
    for k, v in mapping.items():
        if v:
            os.environ[k] = str(v)
