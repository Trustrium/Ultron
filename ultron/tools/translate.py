"""Explicit translation tool — uses the configured LLM provider, so it works with any backend."""
from __future__ import annotations

from ..llm import make_llm_client

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = make_llm_client()
    return _client


def translate(text: str, target_language: str = "english") -> str:
    """Translate `text` to the target language. target_language is a natural-language name
    like 'tamil', 'english', 'hindi', 'spanish', 'french', etc.
    """
    text = (text or "").strip()
    if not text:
        return "Nothing to translate."
    target = (target_language or "english").strip()
    prompt = (
        f"Translate the following text into {target}. "
        "Reply with ONLY the translation, no explanation, no quotes, no prefixes.\n\n"
        f"Text: {text}"
    )
    try:
        client = _get_client()
        # Use the LLMClient.chat directly with no tools — we just want a single text response.
        response = client.chat(
            system="You are a precise translator. Output only the translated text.",
            history=[client.make_user_message(prompt)],
            tools=[],
        )
        out = (response.text or "").strip().strip('"').strip("'")
        return out or "(translation failed: empty response)"
    except Exception as e:
        return f"Translate failed: {e}"
