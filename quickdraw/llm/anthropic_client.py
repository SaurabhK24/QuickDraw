from __future__ import annotations

from typing import Any

import anthropic

from quickdraw.llm.base import LLMClient
from quickdraw.llm.types import LLMResponse


def _serialize_content(content: list[Any]) -> list[dict]:
    serialized: list[dict] = []
    for block in content:
        if hasattr(block, "text"):
            serialized.append({"type": "text", "text": block.text})
        elif getattr(block, "type", None) == "tool_use":
            serialized.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
    return serialized


class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def name(self) -> str:
        return "anthropic"

    def supports_tools(self) -> bool:
        return True

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        model: str,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            resp = self._client.messages.create(**kwargs)
        except anthropic.APIError as e:
            msg = f"Error code: {getattr(e, 'status_code', '?')} - {e}"
            return LLMResponse(stop_reason="error", content=[], error=msg)

        content = _serialize_content(resp.content)
        if resp.stop_reason == "tool_use":
            return LLMResponse(stop_reason="tool_use", content=content)
        return LLMResponse(stop_reason="end_turn", content=content)

