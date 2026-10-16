"""Run a short Python snippet in a fresh subprocess with a wall-clock timeout.

Use cases:
- Quick math / data manipulation
- Date arithmetic
- Regex testing
- Anything the LLM can't compute reliably itself

Safety:
- Runs in a separate Python process, not our main one
- Strict wall-clock timeout (default 5s, capped at 30s)
- Output captured + truncated; no interactive input
"""
from __future__ import annotations
import subprocess
import sys

MAX_OUTPUT = 4000
MAX_TIMEOUT_SECONDS = 30


def run_python(code: str, timeout: int = 5) -> str:
    code = (code or "").strip()
    if not code:
        return "No code provided."
    timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))

    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],   # -I = isolated, no user site / env
            capture_output=True, text=True, timeout=timeout,
            # No shell, no inherited env beyond what subprocess copies; safe.
        )
        out = (result.stdout or "")
        if result.stderr:
            out += "\n[stderr]\n" + result.stderr
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + f"\n... (truncated, exit={result.returncode})"
        return out.strip() or f"(no output, exit={result.returncode})"
    except subprocess.TimeoutExpired:
        return f"Python execution timed out after {timeout}s."
    except Exception as e:
        return f"Python execution failed: {e}"
