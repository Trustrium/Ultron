"""File and shell tools so Ultron can read/write code and run commands.

Safety:
- Shell commands matching DANGEROUS patterns are refused.
- Writes always create parent dirs; never silently overwrite without the caller asking.
"""
import re
import subprocess
from pathlib import Path

MAX_READ_CHARS = 12000   # avoid blowing the context window
MAX_SHELL_OUT = 4000

DANGEROUS_PATTERNS = [
    # Unix-style (still blocked even though we run PowerShell)
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r">\s*/dev/sd",
    r":\(\)\s*\{",                            # fork bomb

    # Windows cmd
    r"\bformat\s+[a-z]:",
    r"\bdel\s+/[sfq]",
    r"\brmdir\s+/s",
    r"\bdiskpart\b",
    r"\bshutdown\s+[/-][srpgh]\b",   # /s shutdown, /r restart, /p power-off, /g, /h
    r"\bbcdedit\b",                   # boot config edits

    # PowerShell — the actual risk surface for us
    r"remove-item\s+.*-recurse",              # rm -rf
    r"remove-item\s+.*-force",
    r"\bri\s+.*-recurse",
    r"format-volume",
    r"clear-disk",
    r"clear-recyclebin",
    r"\bstop-computer\b",
    r"\brestart-computer\b",
    r"set-executionpolicy\s+unrestricted",
    # Remote-code-execution one-liners — block iex/invoke-expression of any
    # subexpression or web fetch (the classic `iex (irm url)` / `iex (iwr url)` /
    # `iex (...DownloadString...)` malware shape).
    r"\biex\s*\(",
    r"invoke-expression\s*\(",
    r"downloadstring",
    r"\bi(rm|wr)\b.*\|\s*iex",                 # irm/iwr ... | iex
    r"start-process.*-verb\s+runas",           # auto-elevation
]


def _is_dangerous(cmd: str) -> bool:
    low = cmd.lower()
    return any(re.search(p, low) for p in DANGEROUS_PATTERNS)


def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    if not p.is_file():
        return f"Not a file: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Could not read {p}: {e}"
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n\n... (truncated, total {len(text)} chars)"
    return f"--- {p} ---\n{text}"


def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {p}."
    except Exception as e:
        return f"Could not write {p}: {e}"


def append_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {p}."
    except Exception as e:
        return f"Could not append to {p}: {e}"


def list_dir(path: str = ".") -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Path not found: {p}"
    if not p.is_dir():
        return f"Not a directory: {p}"
    entries = []
    for item in sorted(p.iterdir()):
        kind = "DIR " if item.is_dir() else "FILE"
        try:
            size = item.stat().st_size if item.is_file() else 0
        except OSError:
            size = 0
        entries.append(f"{kind}  {item.name}  ({size} B)" if item.is_file() else f"{kind}  {item.name}")
    return f"Contents of {p}:\n" + "\n".join(entries) if entries else f"{p} is empty."


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a Windows shell command. Blocks dangerous commands."""
    if _is_dangerous(command):
        return f"Refusing dangerous command: {command}"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout or "") + (("\n[stderr]\n" + result.stderr) if result.stderr else "")
        if len(out) > MAX_SHELL_OUT:
            out = out[:MAX_SHELL_OUT] + f"\n... (truncated, exit={result.returncode})"
        return out.strip() or f"(no output, exit={result.returncode})"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except Exception as e:
        return f"Shell error: {e}"
