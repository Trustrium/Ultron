"""FallbackClient — wraps multiple same-family LLMClients for resilience.

Tries the active provider; on a rate-limit / transient error it transparently
falls through to the next provider (e.g. Groq -> Gemini, both free + OpenAI-compat),
then sticks with whichever worked. This keeps Ultron up when one provider's daily
quota is exhausted.

IMPORTANT: all sub-clients must share the same message format (all OpenAI-compat,
or all Anthropic) since conversation history is built in that format. The factory
enforces this by only pairing same-kind providers.
"""
from __future__ import annotations
import time

from .base import LLMClient, AssistantResponse


def _is_retryable(exc: Exception) -> bool:
    s = f"{type(exc).__name__} {exc}".lower()
    markers = ("rate limit", "ratelimit", "429", "rate_limit",
               "timeout", "timed out", "connection", "temporarily",
               "503", "502", "500", "overloaded", "unavailable",
               # Some Groq Llama models intermittently emit a malformed tool
               # call; falling back to another provider recovers cleanly.
               "tool_use_failed", "failed to call a function")
    return any(m in s for m in markers)


class FallbackClient(LLMClient):
    def __init__(self, clients: list[LLMClient], max_retries_each: int = 1) -> None:
        if not clients:
            raise ValueError("FallbackClient needs at least one client.")
        self.clients = clients
        self.active = 0
        self.max_retries_each = max_retries_each

    # --- format helpers delegate to the active client (same family => compatible) ---
    def make_user_message(self, text: str) -> dict:
        return self.clients[self.active].make_user_message(text)

    def make_assistant_message(self, response: AssistantResponse) -> dict:
        return self.clients[self.active].make_assistant_message(response)

    def make_tool_results(self, results):
        return self.clients[self.active].make_tool_results(results)

    def has_unresolved_tool_calls(self, msg: dict) -> bool:
        return self.clients[self.active].has_unresolved_tool_calls(msg)

    # --- core call with fallback ---
    def chat(self, system: str, history: list, tools: list[dict]) -> AssistantResponse:
        n = len(self.clients)
        last_err: Exception | None = None
        for offset in range(n):
            idx = (self.active + offset) % n
            client = self.clients[idx]
            for attempt in range(self.max_retries_each + 1):
                try:
                    resp = client.chat(system, history, tools)
                    if idx != self.active:
                        print(f"[llm] switched to fallback provider #{idx}")
                        self.active = idx
                    return resp
                except Exception as e:
                    last_err = e
                    if _is_retryable(e):
                        if attempt < self.max_retries_each:
                            time.sleep(1.5 * (attempt + 1))   # brief backoff, then retry same
                            continue
                        break   # move to next provider
                    raise       # non-retryable: surface immediately
        # All providers exhausted
        raise last_err if last_err else RuntimeError("All LLM providers failed.")
