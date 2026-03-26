from __future__ import annotations

from typing import Any

from quickdraw.llm.base import LLMClient
from quickdraw.llm.text_fallback import messages_to_plain_text
from quickdraw.llm.types import LLMResponse


class OpenAIClient(LLMClient):
    """Text-only OpenAI client (no tools yet)."""

    def __init__(self, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def name(self) -> str:
        return "openai"

    def supports_tools(self) -> bool:
        return False

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        model: str,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        plain = messages_to_plain_text(messages)
        oai_messages: list[dict[str, str]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(plain)

        try:
            resp = self._client.chat.completions.create(
                model=model,
                messages=oai_messages,
                max_tokens=max_tokens,
            )
        except Exception as e:
            # Some newer OpenAI models don't accept `max_tokens` and instead expect
            # `max_completion_tokens`. If we see that specific error, retry.
            msg = str(e)
            if (
                "Unsupported parameter: 'max_tokens'" in msg
                or "max_tokens is not supported" in msg
                or "max_completion_tokens" in msg
            ):
                try:
                    resp = self._client.chat.completions.create(
                        model=model,
                        messages=oai_messages,
                        max_completion_tokens=max_tokens,
                    )
                except Exception as e2:
                    return LLMResponse(
                        stop_reason="error",
                        content=[],
                        error=str(e2),
                    )
            else:
                return LLMResponse(stop_reason="error", content=[], error=msg)

        text = (resp.choices[0].message.content or "").strip()
        return LLMResponse(stop_reason="end_turn", content=[{"type": "text", "text": text}])

