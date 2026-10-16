"""Skill macros — save a sequence of tool calls as a named skill and replay later.

Stored at data/skills.json. Each skill = ordered list of {tool, args} dicts.

The brain calls one of three tools:
- create_skill(name, steps)  -> stores it
- run_skill(name)            -> executes each step in order, returns combined output
- list_skills() / delete_skill(name)
"""
from __future__ import annotations
import json
import threading
from pathlib import Path

from ..config import DATA_DIR

SKILLS_FILE = Path(DATA_DIR) / "skills.json"
_lock = threading.Lock()


def _load() -> dict:
    if not SKILLS_FILE.exists():
        return {}
    try:
        return json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    SKILLS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_skill(name: str, steps: list[dict]) -> str:
    """Define a skill. `steps` is a list of {tool: str, args: dict} dicts."""
    name = (name or "").strip()
    if not name:
        return "Skill needs a name."
    if not isinstance(steps, list) or not steps:
        return "Skill needs at least one step."
    cleaned: list[dict] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or "tool" not in step:
            return f"Step {i+1} missing 'tool' field."
        cleaned.append({"tool": str(step["tool"]),
                        "args": step.get("args") or {}})
    with _lock:
        skills = _load()
        skills[name] = cleaned
        _save(skills)
    return f"Skill '{name}' saved with {len(cleaned)} step(s)."


def list_skills() -> str:
    skills = _load()
    if not skills:
        return "No skills defined yet."
    lines = []
    for name, steps in skills.items():
        tools = [s.get("tool", "?") for s in steps]
        lines.append(f"- {name}: {len(steps)} step(s) -> {', '.join(tools)}")
    return "Defined skills:\n" + "\n".join(lines)


def delete_skill(name: str) -> str:
    with _lock:
        skills = _load()
        if name not in skills:
            return f"No skill named '{name}'."
        del skills[name]
        _save(skills)
    return f"Skill '{name}' deleted."


def run_skill(name: str, handlers: dict | None = None) -> str:
    """Execute a saved skill by replaying its steps via the brain's TOOL_HANDLERS."""
    skills = _load()
    if name not in skills:
        return f"No skill named '{name}'. Existing: {', '.join(skills) or '(none)'}"
    if handlers is None:
        # Avoid circular import — fetch lazily.
        from .. import brain as _b
        handlers = _b.TOOL_HANDLERS
    outputs = []
    for i, step in enumerate(skills[name], 1):
        tool = step.get("tool")
        args = step.get("args") or {}
        fn = handlers.get(tool)
        if not fn:
            outputs.append(f"  Step {i} ({tool}): UNKNOWN TOOL — skipped")
            continue
        try:
            result = fn(args)
            outputs.append(f"  Step {i} ({tool}): {str(result)[:200]}")
        except Exception as e:
            outputs.append(f"  Step {i} ({tool}) FAILED: {e}")
    return f"Ran skill '{name}':\n" + "\n".join(outputs)
