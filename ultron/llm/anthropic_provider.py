"""Anthropic (Claude) LLM client implementing the same interface as OpenAICompatClient."""
from __future__ import annotations

from anthropic import Anthropic

from .base import LLMClient, AssistantResponse, ToolCall


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    # --- core call --------------------------------------------------------------
    def chat(self, system: str, history: list, tools: list[dict]) -> AssistantResponse:
        anth_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=anth_tools or None,
            messages=history,
        )
        # Track usage for the GUI status bar.
        try:
            from ..usage import record
            usage = getattr(resp, "usage", None)
            if usage is not None:
                record("anthropic",
                       int(getattr(usage, "input_tokens", 0) or 0),
                       int(getattr(usage, "output_tokens", 0) or 0))
        except Exception:
            pass

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return AssistantResponse(
            text=" ".join(text_parts).strip(),
            tool_calls=tool_calls,
            raw_message=resp.content,    # list of ContentBlocks
        )

    # --- message construction ---------------------------------------------------
    def make_user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def make_assistant_message(self, response: AssistantResponse) -> dict:
        # Anthropic wants the raw content blocks back as-is.
        return {"role": "assistant", "content": response.raw_message}

    def make_tool_results(self, results: list[tuple[str, str]]) -> dict:
        # Anthropic format: ONE user message with a list of tool_result blocks.
        return {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tc_id, "content": str(result)}
                for tc_id, result in results
            ],
        }

    # --- history hygiene --------------------------------------------------------
    def has_unresolved_tool_calls(self, msg: dict) -> bool:
        content = msg.get("content")
        if not isinstance(content, list):
            return False
        for b in content:
            btype = getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else None)
            if btype == "tool_use":
                return True
        return False
