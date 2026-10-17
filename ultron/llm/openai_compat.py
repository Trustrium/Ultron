"""OpenAI-compatible LLM client.

Works with ANY provider that speaks OpenAI's chat-completions API:
    - Groq      (https://api.groq.com/openai/v1)
    - OpenAI    (https://api.openai.com/v1)
    - Ollama    (http://localhost:11434/v1)
    - OpenRouter (https://openrouter.ai/api/v1)
    - Together  (https://api.together.xyz/v1)
    - Gemini    (https://generativelanguage.googleapis.com/v1beta/openai/)
    - vLLM, LM Studio, anything else with the same shape.
"""
from __future__ import annotations
import json
from typing import Any

from openai import OpenAI

from .base import LLMClient, AssistantResponse, ToolCall


class OpenAICompatClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: str | None = None, max_tokens: int = 1024) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self.max_tokens = max_tokens
        # Kept so clone_with_model() can rebuild an identical client on another model.
        self._api_key = api_key
        self._base_url = base_url

    def clone_with_model(self, model: str) -> "OpenAICompatClient":
        clone = OpenAICompatClient(api_key=self._api_key, model=model,
                                   base_url=self._base_url, max_tokens=self.max_tokens)
        clone._provider_id = getattr(self, "_provider_id", "openai_compat")
        return clone

    def _oa_tools(self, tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    # --- core call --------------------------------------------------------------
    def chat(self, system: str, history: list, tools: list[dict]) -> AssistantResponse:
        oa_tools = self._oa_tools(tools)
        messages = [{"role": "system", "content": system}] + history
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.6,
        )
        # Only send tools/tool_choice when we actually have tools — Groq rejects
        # tool_choice=null even when tools is empty.
        if oa_tools:
            kwargs["tools"] = oa_tools
            kwargs["tool_choice"] = "auto"
        resp = self.client.chat.completions.create(**kwargs)
        # Track token usage for the GUI status bar.
        try:
            from ..usage import record
            usage = getattr(resp, "usage", None)
            if usage is not None:
                record(getattr(self, "_provider_id", "openai_compat"),
                       int(getattr(usage, "prompt_tokens", 0) or 0),
                       int(getattr(usage, "completion_tokens", 0) or 0))
        except Exception:
            pass
        msg = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return AssistantResponse(text=(msg.content or "").strip(), tool_calls=tool_calls, raw_message=msg)

    def chat_stream(self, system: str, history: list, tools: list[dict],
                    on_token=None) -> AssistantResponse:
        """True streaming via stream=True. Calls on_token per text delta and
        accumulates streamed tool-call chunks (by index) into ToolCalls.
        Returns the same full AssistantResponse chat() would. On any streaming
        error, falls back to single-shot chat() so the turn still completes."""
        try:
            return self._chat_stream_inner(system, history, tools, on_token)
        except Exception as e:
            print(f"[llm] streaming failed ({e}); falling back to single-shot chat().")
            return self.chat(system, history, tools)

    def _chat_stream_inner(self, system: str, history: list, tools: list[dict],
                           on_token=None) -> AssistantResponse:
        oa_tools = self._oa_tools(tools)
        messages = [{"role": "system", "content": system}] + history
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.6,
            stream=True,
        )
        if oa_tools:
            kwargs["tools"] = oa_tools
            kwargs["tool_choice"] = "auto"
        stream = self.client.chat.completions.create(**kwargs)
        text_parts: list[str] = []
        # Tool-call chunks arrive split across deltas; accumulate per index.
        tc_acc: dict[int, dict] = {}
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                text_parts.append(content)
                if on_token is not None:
                    try:
                        on_token(content)
                    except Exception:
                        pass
            for tc_chunk in (getattr(delta, "tool_calls", None) or []):
                idx = getattr(tc_chunk, "index", 0)
                acc = tc_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc_chunk, "id", None):
                    acc["id"] = tc_chunk.id
                fn = getattr(tc_chunk, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        # Names can ALSO split across chunks — append, don't overwrite.
                        acc["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        acc["arguments"] += fn.arguments
        tool_calls: list[ToolCall] = []
        for idx in sorted(tc_acc):
            acc = tc_acc[idx]
            if not acc["name"]:
                continue
            try:
                args = json.loads(acc["arguments"] or "{}")
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=acc["id"] or f"stream_{idx}",
                                       name=acc["name"], arguments=args))
        return AssistantResponse(text="".join(text_parts).strip(),
                                 tool_calls=tool_calls, raw_message=None)

    # --- message construction ---------------------------------------------------
    def make_user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def make_assistant_message(self, response: AssistantResponse) -> dict:
        out: dict = {"role": "assistant", "content": response.text or ""}
        if response.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in response.tool_calls
            ]
        return out

    def make_tool_results(self, results: list[tuple[str, str]]) -> list[dict]:
        # OpenAI format: one `role: tool` message per tool call.
        return [
            {"role": "tool", "tool_call_id": tc_id, "content": str(result)}
            for tc_id, result in results
        ]

    # --- history hygiene --------------------------------------------------------
    def has_unresolved_tool_calls(self, msg: dict) -> bool:
        return bool(msg.get("tool_calls"))
