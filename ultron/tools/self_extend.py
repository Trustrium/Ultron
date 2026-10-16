"""Self-extension — Ultron writes a NEW plugin tool from a description and hot-loads it.

It asks the LLM to author a plugin file (TOOLS + HANDLERS contract), validates it
parses + imports, writes it to plugins/, and merges it into the live tool registry.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path

from ..llm import make_llm_client
from ..plugins_loader import PLUGINS_DIR

_client = None

_PLUGIN_TEMPLATE_HINT = '''
A plugin file must define module-level TOOLS (list) and HANDLERS (dict). Example:

    """One-line description."""
    def _hello(args: dict) -> str:
        return f"Hello {args.get('name','world')}"

    TOOLS = [
        {
            "name": "say_hello",
            "description": "Greet someone by name.",
            "parameters": {"type":"object","properties":{"name":{"type":"string"}}},
        },
    ]
    HANDLERS = {"say_hello": _hello}

Rules: pure standard-library (or urllib for HTTP) only; no network secrets; handlers
take a single dict arg and return a STRING; tool names must be unique snake_case.
'''


def _safe_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9_]", "_", (name or "").lower()).strip("_")
    return n or "custom_plugin"


def create_plugin(name: str, description: str) -> str:
    """Generate a plugin from a natural-language description, save + hot-load it."""
    name = _safe_name(name)
    description = (description or "").strip()
    if not description:
        return "Describe what the plugin should do."

    global _client
    if _client is None:
        _client = make_llm_client()

    prompt = (
        f"Write a complete Python plugin file for a tool that does the following:\n"
        f"{description}\n\n"
        f"{_PLUGIN_TEMPLATE_HINT}\n"
        "Output ONLY the Python code, no markdown fences, no explanation."
    )
    try:
        resp = _client.chat(
            system="You write small, correct, self-contained Python plugin modules.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        code = (resp.text or "").strip()
    except Exception as e:
        return f"Plugin generation failed: {e}"

    # Strip accidental markdown fences
    code = re.sub(r"^```[a-zA-Z]*\n", "", code)
    code = re.sub(r"\n```\s*$", "", code).strip()

    # Validate it parses
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Generated plugin has a syntax error ({e}); not saved."

    # Must define TOOLS and HANDLERS
    names = {n.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
             for n in node.targets if isinstance(n, ast.Name)}
    if "TOOLS" not in names or "HANDLERS" not in names:
        return "Generated plugin is missing TOOLS or HANDLERS; not saved."

    # Light safety scan — block obviously dangerous calls
    banned = ["os.system", "subprocess", "shutil.rmtree", "eval(", "exec(",
              "__import__", "open(", "remove(", "unlink("]
    low = code.lower()
    hits = [b for b in banned if b in low]
    if hits:
        return (f"Refusing to save plugin — it uses restricted operations: {hits}. "
                "Plugins must be pure/standard-library and side-effect-free for safety.")

    path = PLUGINS_DIR / f"{name}.py"
    if path.exists():
        return f"A plugin named '{name}' already exists. Pick a different name."
    try:
        PLUGINS_DIR.mkdir(exist_ok=True)
        path.write_text(code, encoding="utf-8")
    except Exception as e:
        return f"Could not write plugin: {e}"

    # Hot-load into the live registry
    try:
        from ..plugins_loader import _load_module
        from .. import brain as _b
        mod = _load_module(path)
        tools = getattr(mod, "TOOLS", []) or []
        handlers = getattr(mod, "HANDLERS", {}) or {}
        added = 0
        existing = {t["name"] for t in _b.TOOLS}
        for t in tools:
            tn = t.get("name")
            if tn and tn not in existing and tn in handlers:
                _b.TOOLS.append(t)
                _b.TOOL_HANDLERS[tn] = handlers[tn]
                added += 1
        return (f"Created and loaded plugin '{name}' with {added} new tool(s): "
                f"{', '.join(t.get('name','?') for t in tools)}. Saved to {path}.")
    except Exception as e:
        return f"Plugin saved to {path} but failed to load: {e} (it'll load on next restart)."
