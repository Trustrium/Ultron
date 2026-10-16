"""Computer-use agent — the closed-loop 'Operator' pattern.

Loop: screenshot -> vision model decides the next ACTION -> execute -> re-screenshot -> repeat,
until the model says it's done or we hit the step cap.

Each step the model returns ONE action as JSON:
  {"action":"click","x":..,"y":..,"reason":..}
  {"action":"double_click","x":..,"y":..}
  {"action":"type","text":".."}
  {"action":"key","keys":"ctrl+s"}
  {"action":"scroll","amount":-500}
  {"action":"wait","seconds":1}
  {"action":"done","summary":".."}

Coordinates are in the DOWNSCALED image space; we scale them back to real pixels.
Vision models aren't pixel-perfect, so this is best for large, clear targets and
benefits from the re-observation loop (it can correct after seeing the result).
"""
from __future__ import annotations
import base64
import io
import json
import re
import time

_VISION_WIDTH = 1280


def _screenshot_b64() -> tuple[str, float]:
    from PIL import ImageGrab, Image
    try:
        img = ImageGrab.grab(all_screens=False)
    except TypeError:
        img = ImageGrab.grab()
    rw, rh = img.size
    scale = 1.0
    if rw > _VISION_WIDTH:
        scale = rw / _VISION_WIDTH
        img = img.resize((_VISION_WIDTH, int(rh / scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii"), scale


_SYSTEM = """You are controlling a Windows PC to accomplish a goal. You see a screenshot
each turn and must output exactly ONE next action as compact JSON (no prose around it).

Allowed actions:
  {"action":"click","x":<int>,"y":<int>,"reason":"..."}
  {"action":"double_click","x":<int>,"y":<int>}
  {"action":"type","text":"..."}
  {"action":"key","keys":"enter"}        // or "ctrl+s", "alt+tab", "win+r", etc.
  {"action":"scroll","amount":-500}      // negative = down
  {"action":"wait","seconds":1}
  {"action":"done","summary":"what was accomplished"}

Coordinates are pixels in THIS screenshot. Click element CENTERS. Work in small steps:
look, act, then look again next turn. Call "done" when the goal is achieved or clearly
impossible. Output ONLY the JSON object."""


def _ask_next_action(client, kind: str, goal: str, history: list[str], b64: str) -> dict:
    hist = "\n".join(history[-8:]) if history else "(no actions yet)"
    text = (f"GOAL: {goal}\n\nActions so far:\n{hist}\n\n"
            "Look at the screenshot and return the next single action as JSON.")
    try:
        if kind == "anthropic":
            resp = client.client.messages.create(
                model=client.model, max_tokens=300, system=_SYSTEM,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": text},
                ]}],
            )
            out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        else:
            resp = client.client.chat.completions.create(
                model=client.model, max_tokens=300, temperature=0.1,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]},
                ],
            )
            out = resp.choices[0].message.content or ""
    except Exception as e:
        return {"action": "done", "summary": f"vision call failed: {e}"}

    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return {"action": "done", "summary": f"no action parsed from: {out[:80]}"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"action": "done", "summary": f"bad action json: {out[:80]}"}


def _execute(action: dict, scale: float) -> str:
    from . import automation as auto
    a = action.get("action")
    try:
        if a in ("click", "double_click"):
            x = int(round(float(action["x"]) * scale))
            y = int(round(float(action["y"]) * scale))
            return auto.mouse_click(x, y, clicks=2 if a == "double_click" else 1)
        if a == "type":
            return auto.type_text(action.get("text", ""))
        if a == "key":
            return auto.press_keys(action.get("keys", ""))
        if a == "scroll":
            return auto.scroll(int(action.get("amount", -500)))
        if a == "wait":
            time.sleep(min(float(action.get("seconds", 1)), 5))
            return "waited"
        return f"unknown action: {a}"
    except Exception as e:
        return f"action failed: {e}"


def operate_computer(goal: str, max_steps: int = 10,
                     progress=None) -> str:
    """Closed-loop computer control toward a goal. Returns a summary."""
    from ..llm import make_vision_client
    try:
        kind, client = make_vision_client()
    except Exception as e:
        return f"Computer-use needs a vision model: {e}"

    def emit(m):
        if progress:
            try:
                progress(m)
            except Exception:
                pass

    history: list[str] = []
    emit(f"[operate] goal: {goal}")
    for step in range(max(1, min(int(max_steps), 20))):
        b64, scale = _screenshot_b64()
        action = _ask_next_action(client, kind, goal, history, b64)
        a = action.get("action", "done")
        if a == "done":
            summary = action.get("summary", "Task ended.")
            emit(f"[operate] done: {summary}")
            return f"Computer-use finished: {summary}"
        result = _execute(action, scale)
        log = f"step {step+1}: {a} {({k:v for k,v in action.items() if k!='action'})} -> {result}"
        history.append(log)
        emit(f"[operate] {log}")
        time.sleep(0.6)   # let the UI settle before the next screenshot
    return "Computer-use hit the step limit. Partial progress made:\n" + "\n".join(history[-5:])
