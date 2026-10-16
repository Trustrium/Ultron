"""Factory: read config and produce the right LLM + vision client."""
from __future__ import annotations

from ..config import (
    LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL,
    LLM_FALLBACK_PROVIDER, LLM_FALLBACK_API_KEY, LLM_FALLBACK_MODEL,
    VISION_PROVIDER, VISION_API_KEY, VISION_MODEL, VISION_BASE_URL,
)
from .base import LLMClient


# === Sensible defaults per provider so user can supply just the key =============
PROVIDER_DEFAULTS: dict[str, dict] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "vision_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "vision_model": "gpt-4o",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-sonnet-4",
        "vision_model": "anthropic/claude-sonnet-4",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
        "vision_model": "gemini-2.5-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.3",
        "vision_model": "llava",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "vision_model": "meta-llama/Llama-Vision-Free",
    },
    "anthropic": {
        "base_url": None,
        "model": "claude-sonnet-4-6",
        "vision_model": "claude-sonnet-4-6",
    },
    "openai_compat": {
        # Generic — user must provide both base_url and model.
        "base_url": None,
        "model": None,
        "vision_model": None,
    },
}


def _resolve(provider: str, key_kind: str, override: str) -> str:
    """Return override if non-empty, else the default for this provider, else ''."""
    if override:
        return override
    return PROVIDER_DEFAULTS.get(provider, {}).get(key_kind, "") or ""


def _build_one(provider: str, api_key: str, model_override: str,
               base_url_override: str = "") -> LLMClient:
    """Build a single LLM client for a provider."""
    provider = (provider or "groq").lower()
    model = _resolve(provider, "model", model_override)
    base_url = _resolve(provider, "base_url", base_url_override)
    if not api_key:
        raise RuntimeError(f"API key is empty for provider '{provider}'.")
    if not model:
        raise RuntimeError(f"No model for provider '{provider}'. Set the model in .env.")
    if provider == "anthropic":
        from .anthropic_provider import AnthropicClient
        return AnthropicClient(api_key=api_key, model=model)
    from .openai_compat import OpenAICompatClient
    client = OpenAICompatClient(api_key=api_key, model=model, base_url=base_url or None)
    client._provider_id = provider
    return client


def _is_openai_family(provider: str) -> bool:
    return (provider or "").lower() != "anthropic"


def make_llm_client() -> LLMClient:
    """Build the configured LLM client for the brain — with optional fallback chain."""
    primary_provider = (LLM_PROVIDER or "groq").lower()
    primary = _build_one(primary_provider, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL)

    # Optional fallback — only chained if it's the SAME API family (compatible history).
    if LLM_FALLBACK_PROVIDER and LLM_FALLBACK_API_KEY:
        fb_provider = LLM_FALLBACK_PROVIDER
        if _is_openai_family(primary_provider) == _is_openai_family(fb_provider):
            try:
                fallback = _build_one(fb_provider, LLM_FALLBACK_API_KEY, LLM_FALLBACK_MODEL)
                from .fallback import FallbackClient
                print(f"[llm] fallback enabled: {primary_provider} -> {fb_provider}")
                return FallbackClient([primary, fallback])
            except Exception as e:
                print(f"[llm] fallback disabled ({e}); using primary only.")
        else:
            print(f"[llm] fallback '{fb_provider}' is a different API family from "
                  f"'{primary_provider}'; skipping (history formats would clash).")
    return primary


def make_vision_client():
    """Build a vision-capable client. Defaults to the same provider/key as the brain."""
    provider = (VISION_PROVIDER or LLM_PROVIDER or "groq").lower()
    api_key = VISION_API_KEY or LLM_API_KEY
    model = _resolve(provider, "vision_model", VISION_MODEL)
    base_url = _resolve(provider, "base_url", VISION_BASE_URL)

    if not api_key:
        raise RuntimeError("No API key set for vision (LLM_API_KEY or VISION_API_KEY).")
    if not model:
        raise RuntimeError(f"No vision model for provider '{provider}'. Set VISION_MODEL.")

    if provider == "anthropic":
        from .anthropic_provider import AnthropicClient
        return ("anthropic", AnthropicClient(api_key=api_key, model=model))

    from .openai_compat import OpenAICompatClient
    return ("openai_compat", OpenAICompatClient(api_key=api_key, model=model, base_url=base_url or None))
