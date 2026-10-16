"""Provider-agnostic brain: takes user text, plans, calls tools, returns spoken reply.

Uses an LLMClient (see ultron/llm/) so users can swap providers via .env.
The tool catalog lives in tool_registry.py; this file is the run-loop.
"""
from __future__ import annotations
import datetime as _dt
import re

from .llm import make_llm_client, LLMClient
from .tools import memory as t_memory
from .tools import profile as t_profile
from .personality import get_guidance as _personality_guidance
from . import settings as _settings
from .tool_registry import TOOLS, TOOL_HANDLERS, _load_plugins_once
from .tool_router import select_tools

# Some models (notably Groq's Llama) intermittently emit a malformed tool call
# as plain text inside the reply, e.g. <function=set_profile>{...}</function>.
# Strip any such leaked markup so it is never shown or spoken aloud.
_TOOL_MARKUP_RE = re.compile(r"<function\b.*?</function\s*>", re.DOTALL | re.IGNORECASE)
_TOOL_MARKUP_OPEN_RE = re.compile(r"<function\b.*$", re.DOTALL | re.IGNORECASE)


def _strip_tool_markup(text: str) -> str:
    if not text:
        return text
    cleaned = _TOOL_MARKUP_RE.sub("", text)
    cleaned = _TOOL_MARKUP_OPEN_RE.sub("", cleaned)   # leftover unclosed fragment
    return cleaned.strip()


SYSTEM_PROMPT = """You are Ultron, Rashid Ali's personal super-intelligent PC agent on his Windows PC.

Rules:
- You can hear and speak in BOTH English and Roman Urdu (Urdu written in Latin script). Reply in the SAME language the user just spoke. (Legacy Tamil "ta" still supported if detected.)
- Always address the user as "sir" naturally, not every sentence. Be professional, concise, loyal and calm.
- Execute first with tools, then report briefly in 1-2 sentences. Do not give long technical scripts when a tool can do it.
- Keep voice replies SHORT — 1 to 2 sentences. This is voice, not chat.
- Prefer using a tool over describing what you would do.
- Always confirm what you did in one short sentence so the user hears it.
- Never invent results. If a tool fails, say so honestly.
- For DESTRUCTIVE actions (shutdown, sleep, delete files, uninstall, run risky shell commands,
  send emails or WhatsApp messages), briefly confirm verbally first — unless the user already
  said a confirmation word like "yes", "do it", "go", "okay", "han", "kar do", "theek hai", "ji han".
- For sending messages (WhatsApp/email) ALWAYS read back the recipient + body, then wait
  for confirmation before actually sending.

LEARN ABOUT THE USER — IMPORTANT:
- When the user shares a structured fact about themselves (name, location, work, role,
  birthday, family member, a preference, a goal, an important date), call `set_profile`
  with the right field so you ALWAYS know it. Fields: name, nickname, location, work,
  role, birthday, languages, family, preferences, goals, important_dates, notes.
- For looser facts, use `remember`. For past-conversation lookups, use `recall_similar`.
- Address the user by name/nickname when you know it. Reference their context naturally.

Personality / tone:
{personality}

WHO YOU'RE TALKING TO (their profile):
{profile}

Current local time: {now}

Other things you remember:
{memory}
"""


MAX_HISTORY_MESSAGES = 40


class Brain:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client: LLMClient = client or make_llm_client()
        self.history: list = []
        _load_plugins_once()

    def _system(self) -> str:
        mem = t_memory.memory_summary_for_prompt() or "(nothing yet)"
        prof = t_profile.profile_for_prompt() or "(unknown — ask and use set_profile)"
        personality_id = _settings.get("personality", "ultron")
        return SYSTEM_PROMPT.format(
            now=_dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p"),
            memory=mem,
            profile=prof,
            personality=_personality_guidance(personality_id),
        )

    def _exec_tool(self, name: str, args: dict, lang: str) -> str:
        fn = TOOL_HANDLERS.get(name)
        if not fn:
            return f"Unknown tool: {name}"
        try:
            if name in ("add_reminder", "set_timer", "start_pomodoro"):
                return fn(args, lang=lang)
            return fn(args)
        except Exception as e:
            return f"Tool '{name}' failed: {e}"

    def _trim_history(self) -> None:
        if len(self.history) <= MAX_HISTORY_MESSAGES:
            return
        drop = len(self.history) - MAX_HISTORY_MESSAGES
        # Walk forward to a safe boundary — never start with an orphan tool response.
        while drop < len(self.history):
            m = self.history[drop]
            role = m.get("role")
            if role == "tool":
                drop += 1
                continue
            if role == "assistant" and self.client.has_unresolved_tool_calls(m):
                drop += 1
                continue
            if role == "user" and isinstance(m.get("content"), list):
                # Anthropic-style tool_result block — skip past it.
                if any((isinstance(b, dict) and b.get("type") == "tool_result") for b in m["content"]):
                    drop += 1
                    continue
            break
        self.history = self.history[drop:]

    def _drop_unresolved_tail(self) -> None:
        if not self.history:
            return
        last = self.history[-1]
        if last.get("role") == "assistant" and self.client.has_unresolved_tool_calls(last):
            self.history.pop()
            if self.history and self.history[-1].get("role") == "user":
                self.history.pop()

    def reset(self) -> None:
        self.history = []

    def _exec_calls(self, tool_calls, lang: str) -> list[tuple[str, str]]:
        """Execute tool calls. Runs in parallel when there's more than one (I/O-bound)."""
        if len(tool_calls) == 1:
            tc = tool_calls[0]
            result = self._exec_tool(tc.name, tc.arguments, lang)
            print(f"[tool] {tc.name}({tc.arguments}) -> {str(result)[:200]}")
            return [(tc.id, str(result))]

        from concurrent.futures import ThreadPoolExecutor
        results: list[tuple[str, str]] = [None] * len(tool_calls)

        def _one(idx_tc):
            idx, tc = idx_tc
            r = self._exec_tool(tc.name, tc.arguments, lang)
            print(f"[tool//] {tc.name}({tc.arguments}) -> {str(r)[:120]}")
            return idx, (tc.id, str(r))

        with ThreadPoolExecutor(max_workers=min(len(tool_calls), 6)) as ex:
            for idx, pair in ex.map(_one, list(enumerate(tool_calls))):
                results[idx] = pair
        return results

    def think(self, user_text: str, lang: str = "en") -> str:
        """Run one user turn. Handles multi-step tool calling. Returns final spoken reply.

        Efficiency: the FIRST model call is given only the tools relevant to the
        user's message (dynamic routing) — big token savings. Follow-up calls in
        the same turn use the full set so multi-step plans aren't constrained.
        """
        from .tool_router import select_tools, cap_tools

        self.history.append(self.client.make_user_message(user_text))
        routed = select_tools(user_text, TOOLS,
                              enabled=_settings.get("tool_routing", True))
        # Follow-up calls use the fuller set, but still capped below the
        # provider tool limit (Groq rejects > 128), keeping routed tools.
        followup_tools = cap_tools(TOOLS, prefer=[t["name"] for t in routed])
        try:
            for step in range(6):
                tools_for_call = routed if step == 0 else followup_tools
                response = self.client.chat(self._system(), self.history, tools_for_call)
                self.history.append(self.client.make_assistant_message(response))

                if not response.tool_calls:
                    self._trim_history()
                    return _strip_tool_markup(response.text) or "Done."

                results = self._exec_calls(response.tool_calls, lang)

                tool_msg = self.client.make_tool_results(results)
                if isinstance(tool_msg, list):
                    self.history.extend(tool_msg)
                else:
                    self.history.append(tool_msg)

            self._drop_unresolved_tail()
            return "Sorry, I got stuck in a tool loop."
        except Exception:
            self._drop_unresolved_tail()
            raise
