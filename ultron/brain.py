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
from .voice.language import language_directive

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

# Tools that must NEVER go through the speculative fast-path model, even when
# the request looks like a single direct command. Safety: destructive /
# outbound actions always get the full main-model reasoning + confirmation flow.
FAST_PATH_BLOCKED_TOOLS = {
    "shutdown_pc", "sleep_pc", "delete_file", "delete_reminder", "kill_process",
    "winget_uninstall", "winget_install", "send_email", "send_whatsapp",
    "send_sms", "make_call", "delete_task", "delete_skill", "delete_routine",
    "delete_watch", "delete_habit", "clear_shopping", "forget",
}

# Markers that mean "this is NOT one simple action" — fast path stays off.
_FAST_PATH_MULTI_MARKERS = (
    " and ", " aur ", " phir ", " then ", " uske baad ", " after ", " pehle ",
    " also ", " plus ", ",", ";", " and then ", " uske baad ",
)
_FAST_PATH_QUESTION_MARKERS = (
    "?", " kya ", " kab ", " kaise ", " kahan ", " kitna ", " kaun ",
    " why ", " what ", " how ", " when ", " where ", " which ",
)


def fast_path_eligible(user_text: str) -> bool:
    """True only when the turn is reliably ONE simple, non-destructive,
    non-question direct command (e.g. 'camera kholo', 'open camera').

    Detection is conservative on purpose: the synonym map must yield exactly
    ONE candidate tool, the text must be short, and there must be no
    conjunction / multi-step / question markers. Anything else -> main model.
    Also requires the opt-in LLM_FAST_PATH=1 env flag (default off).
    """
    from . import config as _config
    if not getattr(_config, "LLM_FAST_PATH", False):
        return False
    text = (user_text or "").strip()
    if not text or len(text.split()) > 10:
        return False
    low = f" {text.lower()} "
    if any(m in low for m in _FAST_PATH_MULTI_MARKERS):
        return False
    if any(m in low for m in _FAST_PATH_QUESTION_MARKERS):
        return False
    if text.strip().endswith("?"):
        return False
    from .tool_synonyms import match_synonyms
    matches = match_synonyms(text)
    if len(matches) != 1:
        return False
    if matches[0]["tool"] in FAST_PATH_BLOCKED_TOOLS:
        return False
    return True


class Brain:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client: LLMClient = client or make_llm_client()
        self.history: list = []
        self._fast_client: LLMClient | None = None
        self._fast_client_tried = False
        _load_plugins_once()

    def _get_fast_client(self) -> LLMClient | None:
        """Lazily build the opt-in fast-model client (same provider/key)."""
        if self._fast_client_tried:
            return self._fast_client
        self._fast_client_tried = True
        try:
            from .llm.factory import make_fast_llm_client
            self._fast_client = make_fast_llm_client()
        except Exception as e:
            print(f"[brain] fast client unavailable ({e})")
            self._fast_client = None
        return self._fast_client

    def _system(self, lang: str = "en") -> str:
        mem = t_memory.memory_summary_for_prompt() or "(nothing yet)"
        prof = t_profile.profile_for_prompt() or "(unknown — ask and use set_profile)"
        personality_id = _settings.get("personality", "ultron")
        base = SYSTEM_PROMPT.format(
            now=_dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p"),
            memory=mem,
            profile=prof,
            personality=_personality_guidance(personality_id),
        )
        # Per-turn language directive: reply in the SAME language/script the
        # user just used. This is appended every turn (not baked into the
        # static prompt) because the language changes per turn. Never English
        # unless the user spoke English.
        return base + f"\n\nLANGUAGE — follow strictly: {language_directive(lang)}"

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

    def think(self, user_text: str, lang: str = "en", on_token=None, on_status=None) -> str:
        """Run one user turn. Handles multi-step tool calling. Returns final spoken reply.

        Efficiency: the FIRST model call is given only the tools relevant to the
        user's message (dynamic routing) — big token savings. Follow-up calls in
        the same turn use the full set so multi-step plans aren't constrained.

        Streaming: pass ``on_token`` to receive partial tokens as they arrive
        (first token <1s is the honest target on a healthy connection — not a
        guarantee). The return value is IDENTICAL with or without a callback.

        Status: pass ``on_status`` to receive "understanding" / "doing" /
        "replying" callbacks so the UI can show feedback within milliseconds
        instead of sitting silent during the LLM call.

        Fast path (opt-in LLM_FAST_PATH=1): for a reliably-detected single-tool
        direct command, the FIRST call speculatively uses the small fast model.
        If it does not produce exactly one tool call, that attempt is discarded
        and the main model retries step 0. All later steps always use the main
        model. Complex reasoning never leaves the main model.
        """
        from .tool_router import select_tools, cap_tools

        def _status(s: str) -> None:
            if on_status is not None:
                try:
                    on_status(s)
                except Exception:
                    pass

        self.history.append(self.client.make_user_message(user_text))
        routed = select_tools(user_text, TOOLS,
                              enabled=_settings.get("tool_routing", True))
        # Follow-up calls use the fuller set, but still capped below the
        # provider tool limit (Groq rejects > 128), keeping routed tools.
        followup_tools = cap_tools(TOOLS, prefer=[t["name"] for t in routed])
        try:
            _status("understanding")
            fast_used = False
            for step in range(6):
                tools_for_call = routed if step == 0 else followup_tools
                # Step 0 fast-path attempt (speculative, main model is the safety net).
                if step == 0 and not fast_used and fast_path_eligible(user_text):
                    fast_client = self._get_fast_client()
                    if fast_client is not None:
                        fast_used = True
                        fast_resp = fast_client.chat_stream(
                            self._system(lang), self.history, tools_for_call,
                            on_token=on_token)
                        if len(fast_resp.tool_calls) == 1:
                            response = fast_resp
                        else:
                            # Fast model missed: discard the attempt entirely
                            # (nothing appended to history yet) and retry with
                            # the main model below. No correctness is lost.
                            print("[brain] fast-path miss — retrying with main model")
                            response = None
                        if response is not None:
                            self.history.append(self.client.make_assistant_message(response))
                            if not response.tool_calls:
                                self._trim_history()
                                return _strip_tool_markup(response.text) or "Done."
                            _status("doing")
                            results = self._exec_calls(response.tool_calls, lang)
                            tool_msg = self.client.make_tool_results(results)
                            if isinstance(tool_msg, list):
                                self.history.extend(tool_msg)
                            else:
                                self.history.append(tool_msg)
                            continue
                # Main-model call (normal path, or fast-path retry).
                if on_token is not None:
                    response = self.client.chat_stream(
                        self._system(lang), self.history, tools_for_call,
                        on_token=on_token)
                else:
                    response = self.client.chat(self._system(lang), self.history, tools_for_call)
                self.history.append(self.client.make_assistant_message(response))

                if not response.tool_calls:
                    _status("replying")
                    self._trim_history()
                    return _strip_tool_markup(response.text) or "Done."

                _status("doing")
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
