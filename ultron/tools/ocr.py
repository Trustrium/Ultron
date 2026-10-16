"""OCR — extract text from screen or image file.

Three-tier strategy:
1. If `pytesseract` + Tesseract binary are installed, use them (fast, local, free)
2. Else fall back to the configured multimodal LLM (Llama 4 Scout via Groq, etc.)
3. Else return a helpful install hint
"""
from __future__ import annotations
import base64
import io
from pathlib import Path


def _grab_screen_pil():
    from PIL import ImageGrab
    try:
        return ImageGrab.grab(all_screens=True)
    except TypeError:
        return ImageGrab.grab()


def _load_pil(path: str):
    from PIL import Image
    return Image.open(path).convert("RGB")


def _tesseract_ocr(img) -> str | None:
    """Try local Tesseract via pytesseract. Returns None if unavailable."""
    try:
        import pytesseract
    except ImportError:
        return None
    try:
        text = pytesseract.image_to_string(img, lang="eng+tam")
        return (text or "").strip()
    except pytesseract.TesseractNotFoundError:
        return None
    except Exception as e:
        return f"(tesseract error: {e})"


def _llm_ocr(img) -> str:
    """Fallback: send image to the configured vision client and ask for plain text extraction."""
    from ..llm import make_vision_client
    try:
        kind, client = make_vision_client()
    except Exception as e:
        return f"OCR fallback unavailable (no vision client): {e}"

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    prompt = (
        "Extract ALL visible text from this image, exactly as it appears. "
        "Preserve line breaks. Do not summarize, comment, or add anything else. "
        "If no text is visible, reply 'NO TEXT'."
    )
    try:
        if kind == "anthropic":
            resp = client.client.messages.create(
                model=client.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        # OpenAI-compat
        resp = client.client.chat.completions.create(
            model=client.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            temperature=0.1,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"LLM OCR failed: {e}"


def ocr_screen(question: str = "") -> str:
    """OCR the whole screen. If question is provided, return only relevant extracted text."""
    img = _grab_screen_pil()
    return _do_ocr(img, question)


def ocr_image(path: str, question: str = "") -> str:
    """OCR a local image file."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    img = _load_pil(str(p))
    return _do_ocr(img, question)


def _do_ocr(img, question: str) -> str:
    text = _tesseract_ocr(img)
    if text is None:
        # Tesseract not installed at all — fall back to LLM vision
        text = _llm_ocr(img)
        if not text or text.strip().upper() == "NO TEXT":
            return "No text detected in the image."
        return ("(via LLM vision)\n" + text) if not question else _filter_by_question(text, question)
    if not text:
        return "No text detected in the image."
    return _filter_by_question(text, question) if question else text


def _filter_by_question(text: str, question: str) -> str:
    """Lightweight: return relevant matching lines if a question is given."""
    q_tokens = [t.lower() for t in question.split() if len(t) > 2]
    if not q_tokens:
        return text
    matches = []
    for line in text.splitlines():
        low = line.lower()
        if any(t in low for t in q_tokens):
            matches.append(line.strip())
    if matches:
        return "\n".join(matches)
    return text   # nothing matched — return full text
