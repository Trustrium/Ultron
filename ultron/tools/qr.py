"""QR code generation — make a QR for text / URL / WiFi, saved as PNG to Desktop."""
from __future__ import annotations
import datetime as _dt
from pathlib import Path


def _desktop() -> Path:
    home = Path.home()
    for c in (home / "OneDrive" / "Desktop", home / "Desktop", home):
        if c.exists():
            return c
    return home


def generate_qr(data: str, path: str = "") -> str:
    """Generate a QR code PNG encoding `data`."""
    data = (data or "").strip()
    if not data:
        return "Provide text or a URL to encode."
    try:
        import qrcode
    except ImportError:
        return "QR needs the qrcode package — run: pip install qrcode"
    if path:
        out = Path(path).expanduser()
        if out.suffix.lower() != ".png":
            out = out.with_suffix(".png")
    else:
        out = _desktop() / f"qr_{_dt.datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        img = qrcode.make(data)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out))
        return f"QR code for '{data[:50]}' saved to {out}"
    except Exception as e:
        return f"QR generation failed: {e}"


def generate_wifi_qr(ssid: str, password: str, security: str = "WPA", path: str = "") -> str:
    """Generate a QR that phones can scan to join a WiFi network."""
    if not ssid:
        return "Provide the WiFi network name (SSID)."
    payload = f"WIFI:T:{security};S:{ssid};P:{password};;"
    return generate_qr(payload, path)
