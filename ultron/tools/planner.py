"""Task planner — break a high-level goal into concrete steps WITHOUT executing them.

Useful for: "how would you do X?", or for the user to review a plan before
launching the autonomous agent.
"""
from __future__ import annotations

from ..llm import make_llm_client

_client = None


def plan_task(goal: str) -> str:
    goal = (goal or "").strip()
    if not goal:
        return "Provide a goal to plan."
    global _client
    if _client is None:
        _client = make_llm_client()
    prompt = (
        f"Break this goal into a short, concrete numbered plan of steps that an assistant "
        f"with computer-control tools (open apps, web search, files, screen clicking, "
        f"typing, email, calendar) could execute. Keep it to 3-8 steps. Be specific.\n\n"
        f"GOAL: {goal}"
    )
    try:
        r = _client.chat(
            system="You are a planning assistant. Output a tight, executable numbered plan.",
            history=[_client.make_user_message(prompt)],
            tools=[],
        )
        return (r.text or "").strip() or "(empty plan)"
    except Exception as e:
        return f"Planning failed: {e}"
