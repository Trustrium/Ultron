"""Install / uninstall / search apps via Windows winget."""
import subprocess


def winget_search(query: str) -> str:
    try:
        result = subprocess.run(
            ["winget", "search", query, "--accept-source-agreements"],
            capture_output=True, text=True, timeout=30,
        )
        out = result.stdout.strip() or result.stderr.strip()
        return out[:2000] if out else "No results."
    except FileNotFoundError:
        return "winget is not installed. Install it from the Microsoft Store ('App Installer')."
    except Exception as e:
        return f"winget search failed: {e}"


def winget_install(package_id: str) -> str:
    """Install by exact package ID (e.g. 'Google.Chrome', 'Mozilla.Firefox')."""
    try:
        result = subprocess.run(
            ["winget", "install", "--id", package_id, "-e",
             "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=600,
        )
        out = (result.stdout or "") + (result.stderr or "")
        ok = result.returncode == 0
        msg = "Installed." if ok else "Install failed."
        return f"{msg}\n{out.strip()[:1500]}"
    except Exception as e:
        return f"winget install failed: {e}"


def winget_uninstall(package_id: str) -> str:
    try:
        result = subprocess.run(
            ["winget", "uninstall", "--id", package_id, "-e"],
            capture_output=True, text=True, timeout=300,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip()[:1500] or f"Done (exit={result.returncode})."
    except Exception as e:
        return f"winget uninstall failed: {e}"
