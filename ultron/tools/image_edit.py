"""Image editing — resize, convert format, rotate. Uses Pillow (already a dependency)."""
from __future__ import annotations
from pathlib import Path


def _open(path: str):
    from PIL import Image
    p = Path(path).expanduser()
    if not p.exists():
        return None, f"File not found: {p}"
    try:
        return Image.open(p), ""
    except Exception as e:
        return None, f"Could not open image: {e}"


def _out_path(src: str, suffix: str, new_ext: str = "") -> Path:
    p = Path(src).expanduser()
    ext = new_ext or p.suffix
    if not ext.startswith("."):
        ext = "." + ext
    return p.with_name(f"{p.stem}{suffix}{ext}")


def resize_image(path: str, width: int = 0, height: int = 0) -> str:
    """Resize. If only one dimension is given, keep aspect ratio."""
    img, err = _open(path)
    if err:
        return err
    try:
        w0, h0 = img.size
        w = int(width) if width else 0
        h = int(height) if height else 0
        if w and not h:
            h = int(h0 * (w / w0))
        elif h and not w:
            w = int(w0 * (h / h0))
        elif not w and not h:
            return "Provide width and/or height."
        from PIL import Image
        out = img.resize((w, h), Image.LANCZOS)
        dst = _out_path(path, f"_{w}x{h}")
        out.save(dst)
        return f"Resized to {w}x{h}: {dst}"
    except Exception as e:
        return f"Resize failed: {e}"


def convert_image(path: str, to_format: str = "png") -> str:
    """Convert to another format (png/jpg/webp/bmp/gif)."""
    img, err = _open(path)
    if err:
        return err
    fmt = to_format.lower().lstrip(".")
    try:
        rgb = img.convert("RGB") if fmt in ("jpg", "jpeg") else img
        dst = _out_path(path, "", new_ext=fmt)
        save_fmt = "JPEG" if fmt in ("jpg", "jpeg") else fmt.upper()
        rgb.save(dst, save_fmt)
        return f"Converted to {fmt}: {dst}"
    except Exception as e:
        return f"Convert failed: {e}"


def rotate_image(path: str, degrees: int = 90) -> str:
    img, err = _open(path)
    if err:
        return err
    try:
        out = img.rotate(-int(degrees), expand=True)   # negative = clockwise
        dst = _out_path(path, f"_rot{degrees}")
        out.save(dst)
        return f"Rotated {degrees}°: {dst}"
    except Exception as e:
        return f"Rotate failed: {e}"
