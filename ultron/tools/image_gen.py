"""Image generation via Pollinations.ai — free, no API key required.

Saves the generated PNG to the user's Desktop and returns the path.
"""
from __future__ import annotations
import datetime as _dt
import urllib.parse
import urllib.request
from pathlib import Path


def _desktop() -> Path:
    home = Path.home()
    for c in (home / "OneDrive" / "Desktop", home / "Desktop", home):
        if c.exists():
            return c
    return home


def generate_image(prompt: str, width: int = 1024, height: int = 1024,
                   model: str = "flux") -> str:
    """Generate an image and save it to Desktop. Returns the saved path."""
    prompt = (prompt or "").strip()
    if not prompt:
        return "Please provide a prompt."
    try:
        w = max(256, min(int(width), 2048))
        h = max(256, min(int(height), 2048))
    except (TypeError, ValueError):
        w, h = 1024, 1024

    safe = urllib.parse.quote_plus(prompt)
    # Pollinations: https://image.pollinations.ai/prompt/<prompt>?width=...&height=...&model=...
    url = (
        f"https://image.pollinations.ai/prompt/{safe}"
        f"?width={w}&height={h}&model={urllib.parse.quote(model)}&nologo=true"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Ultronimage/7.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            content_type = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read()
    except Exception as e:
        return f"Image generation failed: {e}"

    # Pollinations serves JPEG; pick the extension from the actual bytes/header
    # so the file isn't a JPEG mislabeled as .png.
    if data[:3] == b"\xff\xd8\xff" or "jpeg" in content_type or "jpg" in content_type:
        ext = "jpg"
    elif data[:4] == b"\x89PNG" or "png" in content_type:
        ext = "png"
    else:
        return "Image generation failed: server did not return a valid image."

    out_path = _desktop() / f"ultron_img_{_dt.datetime.now():%Y%m%d_%H%M%S}.{ext}"
    try:
        out_path.write_bytes(data)
        return f"Image saved to {out_path}"
    except Exception as e:
        return f"Image generation failed: {e}"
