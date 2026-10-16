"""Vision-guided UI automation — find an on-screen element by description and click it.

Pipeline:
  1. Screenshot the screen at full resolution.
  2. Downscale to a known width, remembering the scale factor.
  3. Ask the configured vision model for the pixel coordinates of the described element.
  4. Scale coordinates back to real screen pixels.
  5. Optionally click there.

Vision models aren't pixel-perfect, so this targets large, clearly-described targets
(buttons, fields, icons). The brain should confirm before clicking.
"""
from __future__ import annotations
import base64
import io
import json
import re

from ..llm import make_vision_client

_VISION_WIDTH = 1280   # downscale target; coords returned in this space then scaled up


def _grab_and_encode() -> tuple[str, float, tuple[int, int]]:
    """Return (base64_png, scale_factor, (real_w, real_h)). scale = real/scaled."""
    from PIL import ImageGrab, Image
    try:
        img = ImageGrab.grab(all_screens=False)   # primary monitor only for coord sanity
    except TypeError:
        img = ImageGrab.grab()
    real_w, real_h = img.size
    scale = 1.0
    if real_w > _VISION_WIDTH:
        scale = real_w / _VISION_WIDTH
        new_size = (_VISION_WIDTH, int(real_h / scale))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return b64, scale, (real_w, real_h)


def _ask_coords(b64: str, description: str) -> dict:
    """Ask the vision model for {x, y} of the element. Returns dict or {'error':..}."""
    kind, client = make_vision_client()
    prompt = (
        f"This is a screenshot. Find the UI element described as: \"{description}\".\n"
        "Reply with ONLY a compact JSON object giving the pixel coordinates of its CENTER "
        "in THIS image, like {\"x\": 640, \"y\": 360}. "
        "If you cannot find it, reply {\"error\": \"not found\"}. No other text."
    )
    try:
        if kind == "anthropic":
            resp = client.client.messages.create(
                model=client.model, max_tokens=100,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        else:
            resp = client.client.chat.completions.create(
                model=client.model, max_tokens=100, temperature=0.0,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]}],
            )
            text = resp.choices[0].message.content or ""
    except Exception as e:
        return {"error": f"vision call failed: {e}"}

    m = re.search(r"\{[^}]*\}", text)
    if not m:
        return {"error": f"no coordinates in response: {text[:80]}"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"error": f"bad json: {text[:80]}"}


def find_on_screen(description: str) -> str:
    """Locate (but don't click) an element. Returns real-screen coordinates or an error."""
    b64, scale, (rw, rh) = _grab_and_encode()
    coords = _ask_coords(b64, description)
    if "error" in coords:
        return f"Could not locate '{description}': {coords['error']}"
    try:
        x = int(round(float(coords["x"]) * scale))
        y = int(round(float(coords["y"]) * scale))
    except (KeyError, TypeError, ValueError):
        return f"Vision returned unusable coordinates: {coords}"
    x = max(0, min(x, rw - 1))
    y = max(0, min(y, rh - 1))
    return f"Found '{description}' at ({x}, {y})."


def click_on_screen(description: str, button: str = "left", double: bool = False) -> str:
    """Find an element by description and click it."""
    b64, scale, (rw, rh) = _grab_and_encode()
    coords = _ask_coords(b64, description)
    if "error" in coords:
        return f"Could not find '{description}' to click: {coords['error']}"
    try:
        x = int(round(float(coords["x"]) * scale))
        y = int(round(float(coords["y"]) * scale))
    except (KeyError, TypeError, ValueError):
        return f"Vision returned unusable coordinates: {coords}"
    x = max(0, min(x, rw - 1))
    y = max(0, min(y, rh - 1))
    try:
        from .automation import mouse_click
        clicks = 2 if double else 1
        result = mouse_click(x, y, button=button, clicks=clicks)
        return f"Clicked '{description}' at ({x}, {y}). {result}"
    except Exception as e:
        return f"Found '{description}' at ({x},{y}) but click failed: {e}"
