"""Ultron Commander — the planning brain that makes Ultron feel like AGI.

Pipeline: Understand -> Plan -> Execute -> Verify -> Report.

- Understand: detect intent + language (English / Roman Urdu) + target + risk.
- Plan: expand one natural command into ordered, safe steps.
- Execute: run steps through tool handlers (or dry-run for preview).
- Verify: check each step's result; stop on failure, never invent success.
- Report: 1-2 sentence summary, addressing the user as "sir".

This module is dependency-free (stdlib only) so it can be unit-tested
without an LLM key. The Brain calls it for multi-step commands; the
Command Center plugin exposes it as tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

# --- Intent detection (English + Roman Urdu) --------------------------------

_INTENTS = [
    ("open_app", ["open", "launch", "start", "kholo", "khol", "chalu", "chala"]),
    ("close_app", ["close", "band karo", "band", "quit", "exit"]),
    ("find_file", ["find", "search", "dhoondo", "talash", "locate"]),
    ("delete_file", ["delete", "remove", "mitao", "delete karo", "erase"]),
    ("briefing", ["briefing", "brief", "summary", "khabar", "update", "status"]),
    ("reminder", ["remind", "reminder", "yaad", "yaad dilao", "alert"]),
    ("system_health", ["health", "system", "cpu", "ram", "battery", "disk"]),
    ("web_search", ["search web", "google", "web", "internet", "batao", "maloom"]),
    ("organize", ["organize", "clean", "saaf", "arrange", "sort"]),
    ("shutdown", ["shutdown", "shut down", "power off", "band karo pc"]),
    ("lock", ["lock", "lock pc", "lock karo"]),
    ("screenshot", ["screenshot", "screen shot", "screen ki photo"]),
]

_RISK_WORDS = ["delete", "remove", "shutdown", "format", "uninstall", "kill", "mitao", "erase"]

_ROMAN_URDU_MARKERS = [
    "kholo", "band", "karo", "batao", "yaad", "dhoondo", "kya", "kaisa",
    "kab", "kahan", "kitna", "chahiye", "kar do", "theek", "han", "ji",
]


@dataclass
class UltronPlan:
    original: str
    intent: str
    language: str  # "en" | "roman_urdu"
    target: str
    steps: list[str] = field(default_factory=list)
    needs_confirmation: bool = False
    risk: str = "low"  # low | medium | high


def detect_language(text: str) -> str:
    low = (text or "").lower()
    if any(w in low for w in _ROMAN_URDU_MARKERS):
        return "roman_urdu"
    return "en"


def build_plan(text: str) -> UltronPlan:
    """Alias for parse_command — build a plan from a natural command."""
    return parse_command(text)


def parse_command(text: str) -> UltronPlan:
    """Parse a single natural command into an UltronPlan."""
    raw = (text or "").strip()
    low = raw.lower()
    language = detect_language(raw)
    intent = "chat"
    for name, keywords in _INTENTS:
        if any(k in low for k in keywords):
            intent = name
            break
    # Target: text after the intent keyword, or full text for chat
    target = raw
    for name, keywords in _INTENTS:
        if name == intent:
            for k in keywords:
                if k in low:
                    idx = low.find(k)
                    target = raw[idx + len(k):].strip(" :,-")
                    break
            break
    if not target:
        target = raw
    needs_confirm = any(w in low for w in _RISK_WORDS) or intent in ("delete_file", "shutdown")
    risk = "high" if intent in ("delete_file", "shutdown") else ("medium" if needs_confirm else "low")
    steps = _steps_for(intent, target, language)
    return UltronPlan(original=raw, intent=intent, language=language, target=target,
                      steps=steps, needs_confirmation=needs_confirm, risk=risk)


def _steps_for(intent: str, target: str, language: str) -> list[str]:
    t = target or "that"
    if intent == "open_app":
        return [f"Find app: {t}", f"Launch app: {t}", "Verify window is focused"]
    if intent == "close_app":
        return [f"Find window: {t}", f"Close window: {t}", "Verify closed"]
    if intent == "find_file":
        return [f"Search by name: {t}", "Search by content if needed", "List matches"]
    if intent == "delete_file":
        return [f"Locate file: {t}", "Confirm with sir (verbal)", "Move to Recycle Bin (never permanent delete)", "Verify in Recycle Bin"]
    if intent == "briefing":
        return ["System health", "Reminders", "Projects status", "Compose briefing"]
    if intent == "reminder":
        return [f"Parse time + text: {t}", "Save reminder", "Confirm back to sir"]
    if intent == "system_health":
        return ["CPU / RAM / Disk / Battery", "Summarize"]
    if intent == "web_search":
        return [f"Search web: {t}", "Fetch top sources", "Summarize in 2-3 lines"]
    if intent == "organize":
        return ["Scan Downloads / Desktop", "Group by type", "Move to folders", "Report counts"]
    if intent == "shutdown":
        return ["Confirm with sir", "Save work reminder", "Shutdown"]
    if intent == "lock":
        return ["Lock workstation", "Verify locked"]
    if intent == "screenshot":
        return ["Capture screen", "Save + show path"]
    return ["Understand request", "Use best tool", "Report result"]


def format_plan(plan: UltronPlan) -> str:
    lang = "Roman Urdu" if plan.language == "roman_urdu" else "English"
    lines = [f"Plan ({plan.intent} | {lang} | risk: {plan.risk}):"]
    for i, s in enumerate(plan.steps, 1):
        lines.append(f"  {i}. {s}")
    if plan.needs_confirmation:
        lines.append("  -> Needs your confirmation first, sir.")
    return "\n".join(lines)


def format_report(plan: UltronPlan, results: list[str]) -> str:
    if plan.language == "roman_urdu":
        head = "Ho gaya, sir."
    else:
        head = "Done, sir."
    body = "; ".join(results) if results else "No steps executed."
    return f"{head} {body}"


class UltronCommander:
    """Execute an UltronPlan step-by-step with verification.

    executor: callable(step_text, plan) -> (ok: bool, detail: str)
    If no executor is given, steps are planned only (dry-run).
    """

    def __init__(self, executor: Callable[[str, UltronPlan], tuple[bool, str]] | None = None):
        self.executor = executor

    def run(self, text: str, dry_run: bool = False) -> dict:
        plan = parse_command(text)
        if dry_run or self.executor is None:
            return {"plan": plan, "preview": format_plan(plan), "executed": False}
        results: list[str] = []
        for step in plan.steps:
            # Confirmation steps never auto-execute — they pause for sir.
            if "Confirm" in step or "confirm" in step.lower():
                results.append(f"{step} — awaiting confirmation")
                continue
            try:
                ok, detail = self.executor(step, plan)
            except Exception as e:  # never crash the commander
                ok, detail = False, f"error: {e}"
            results.append(f"{'OK' if ok else 'FAILED'}: {step} — {detail}")
            if not ok:
                break
        return {
            "plan": plan,
            "results": results,
            "report": format_report(plan, results),
            "executed": True,
        }
