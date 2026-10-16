"""Test a provider config — used by the Settings dialog's 'Test' button."""
from __future__ import annotations


def test_provider(provider: str, api_key: str, model: str = "", base_url: str = "") -> tuple[bool, str]:
    """Make a tiny chat call to verify the key/model work. Returns (ok, message)."""
    from .factory import PROVIDER_DEFAULTS

    if not api_key:
        return False, "API key is empty."

    defaults = PROVIDER_DEFAULTS.get(provider, {})
    if not model:
        model = defaults.get("model") or ""
    if not base_url:
        base_url = defaults.get("base_url") or ""
    if not model:
        return False, f"No default model for provider '{provider}'. Set a model."

    try:
        if provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model,
                max_tokens=20,
                messages=[{"role": "user", "content": "Say 'ok'."}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
            return True, f"Connected. Model replied: {text[:60]}"

        # openai_compat (everything else)
        from openai import OpenAI
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": "Say 'ok'."}],
        )
        text = (resp.choices[0].message.content or "").strip()
        return True, f"Connected. Model replied: {text[:60]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
