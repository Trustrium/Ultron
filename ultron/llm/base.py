"""Provider-agnostic LLM interface for chat-with-tools.

Each concrete provider (OpenAI-compat, Anthropic, ...) implements LLMClient.
The Brain class only touches the abstract interface — no provider-specific code there.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """One tool invocation the model wants to make."""
    id: str
    name: str
    arguments: dict


@dataclass
class AssistantResponse:
    """One round-trip response from the model."""
    text: str                                # Spoken/printable text (may be empty when only tool_calls)
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: object = None               # Provider-native object — append back into history as-is


# === Neutral tool spec used by Brain ============================================
# A tool is described as:
#   {
#       "name": "open_app",
#       "description": "...",
#       "parameters": {"type": "object", "properties": {...}, "required": [...]}
#   }
# Each provider converts this to its own format.


class LLMClient(ABC):
    """Abstract interface every provider implements."""

    # --- core call --------------------------------------------------------------
    @abstractmethod
    def chat(self, system: str, history: list, tools: list[dict]) -> AssistantResponse:
        """Send one chat round. `tools` is the neutral spec; client converts internally."""

    def chat_stream(self, system: str, history: list, tools: list[dict],
                    on_token=None) -> AssistantResponse:
        """Streaming variant of chat(): invokes ``on_token(text_chunk)`` as tokens
        arrive and returns the same full AssistantResponse as chat().

        Default implementation: single-shot chat() + one on_token call with the
        full text. Providers with true streaming (OpenAI-compat) override this
        so the first token arrives in <1s (honest target — network/provider
        dependent) instead of waiting for the whole reply. Callers MUST treat
        the return value identically to chat()'s.
        """
        resp = self.chat(system, history, tools)
        if on_token is not None and resp.text:
            try:
                on_token(resp.text)
            except Exception:
                pass
        return resp

    def clone_with_model(self, model: str) -> "LLMClient":
        """Return a client of the same provider/key pointed at another model
        (used for the opt-in fast-path model). Default: same client."""
        return self

    # --- message construction ---------------------------------------------------
    @abstractmethod
    def make_user_message(self, text: str) -> dict:
        """Build a user-turn message in this provider's history format."""

    @abstractmethod
    def make_assistant_message(self, response: AssistantResponse) -> dict:
        """Build an assistant-turn message (text + tool_calls) for history."""

    @abstractmethod
    def make_tool_results(self, results: list[tuple[str, str]]):
        """Convert [(tool_call_id, result_text), ...] into one or more history messages."""

    # --- history hygiene --------------------------------------------------------
    @abstractmethod
    def has_unresolved_tool_calls(self, last_assistant_msg: dict) -> bool:
        """True if the assistant message has tool_calls with no follow-up tool_results yet."""
