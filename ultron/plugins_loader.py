"""Plugin discovery + loading.

Plugins live in a top-level `plugins/` directory next to ultron_app.py.
Each plugin is a single .py file (or package with __init__.py) that exposes:

    TOOLS    -- list[dict] of tool specs in the neutral format used by brain.py
                  {"name", "description", "parameters"}
    HANDLERS -- dict[str, callable]   tool_name -> handler(args_dict)

Plugins can also define an optional `setup()` function called once after
import (good place to e.g. cache an HTTP session). Errors during load are
logged but never crash the app.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"


def discover_plugin_modules() -> list[Path]:
    if not PLUGINS_DIR.exists():
        return []
    out: list[Path] = []
    for p in sorted(PLUGINS_DIR.iterdir()):
        if p.name.startswith("_") or p.name.startswith("."):
            continue
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir() and (p / "__init__.py").exists():
            out.append(p / "__init__.py")
    return out


def _load_module(path: Path):
    name = f"ultron_plugin_{path.parent.name if path.name == '__init__.py' else path.stem}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_plugins() -> tuple[list[dict], dict]:
    """Return (plugin_tools, plugin_handlers).

    Caller (brain.py) merges these into its own TOOLS + TOOL_HANDLERS.
    Plugins cannot shadow built-in tool names — those are skipped with a warning.
    """
    all_tools: list[dict] = []
    all_handlers: dict = {}
    seen_names: set[str] = set()

    for path in discover_plugin_modules():
        try:
            mod = _load_module(path)
        except Exception as e:
            print(f"[plugins] failed to load {path.name}: {e}")
            continue

        tools = getattr(mod, "TOOLS", None) or []
        handlers = getattr(mod, "HANDLERS", None) or {}
        if not tools or not handlers:
            print(f"[plugins] {path.name}: no TOOLS or HANDLERS exported — skipped")
            continue

        # Run optional setup
        setup = getattr(mod, "setup", None)
        if callable(setup):
            try:
                setup()
            except Exception as e:
                print(f"[plugins] {path.name}.setup() failed: {e}")

        # Validate + merge
        accepted = 0
        for t in tools:
            name = t.get("name")
            if not name or name in seen_names:
                continue
            if name not in handlers:
                print(f"[plugins] {path.name}: tool '{name}' has no handler — skipped")
                continue
            all_tools.append(t)
            all_handlers[name] = handlers[name]
            seen_names.add(name)
            accepted += 1
        print(f"[plugins] loaded '{path.stem}' — {accepted} tool(s)")

    return all_tools, all_handlers


def reserved_names_check(builtin_names: set, plugin_tools: list[dict]) -> list[dict]:
    """Drop any plugin tool whose name collides with a built-in tool. Returns filtered list."""
    out = []
    for t in plugin_tools:
        if t.get("name") in builtin_names:
            print(f"[plugins] skipped tool '{t.get('name')}' — already a built-in")
            continue
        out.append(t)
    return out
