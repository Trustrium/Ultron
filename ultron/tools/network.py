"""Network info: public IP, local IP, WiFi SSID, connectivity check."""
from __future__ import annotations
import socket
import subprocess
import urllib.request


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "unknown"


def public_ip() -> str:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Ultron/12.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip:
                    return ip
        except Exception:
            continue
    return "unavailable"


def wifi_info() -> str:
    """Current WiFi SSID + signal (Windows netsh)."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
        )
        out = result.stdout
        ssid = signal = ""
        for line in out.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and "bssid" not in line.lower():
                ssid = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.lower().startswith("signal"):
                signal = line.split(":", 1)[1].strip() if ":" in line else ""
        if ssid:
            return f"WiFi: {ssid}" + (f" (signal {signal})" if signal else "")
        return "Not connected to WiFi (or no wireless adapter)."
    except Exception as e:
        return f"WiFi info failed: {e}"


def check_internet() -> str:
    """Quick connectivity + rough latency check."""
    import time
    host = "8.8.8.8"
    try:
        start = time.time()
        s = socket.create_connection((host, 53), timeout=5)
        s.close()
        ms = (time.time() - start) * 1000
        return f"Internet: connected (reached {host} in {ms:.0f} ms)."
    except Exception:
        return "Internet: NOT connected (could not reach 8.8.8.8)."


def network_info() -> str:
    """Combined network summary."""
    parts = [
        check_internet(),
        f"Local IP: {local_ip()}",
        f"Public IP: {public_ip()}",
        wifi_info(),
    ]
    return "\n".join(parts)
