"""Provider-agnostic screen vision.

Uses whatever vision provider is configured (defaults to the LLM provider).
"""
import base64
import io

from ..llm import make_vision_client


_client = None
_provider_kind = None


def _get() -> tuple[str, object]:
    """Lazily instantiate the vision client (so import order doesn't matter)."""
    global _client, _provider_kind
    if _client is None:
        _provider_kind, _client = make_vision_client()
    return _provider_kind, _client


def _grab_screenshot_b64() -> str:
    from PIL import ImageGrab, Image
    try:
        img = ImageGrab.grab(all_screens=True)
    except TypeError:
        img = ImageGrab.grab()
    max_side = 1600
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def describe_screen(question: str = "") -> str:
    try:
        b64 = _grab_screenshot_b64()
    except Exception as e:
        return f"Could not capture screen: {e}"

    prompt = question.strip() or "Describe what's on this screen in 1-2 short sentences."
    try:
        kind, client = _get()
    except Exception as e:
        return f"Vision provider not configured: {e}"

    try:
        if kind == "anthropic":
            resp = client.client.messages.create(
                model=client.model,
                max_tokens=400,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip() \
                   or "I couldn't make out the screen."

        # openai_compat (Groq/OpenAI/Gemini/etc.)
        resp = client.client.chat.completions.create(
            model=client.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            max_tokens=400,
            temperature=0.4,
        )
        return (resp.choices[0].message.content or "").strip() or "I couldn't make out the screen."
    except Exception as e:
        return f"Vision call failed: {e}"
