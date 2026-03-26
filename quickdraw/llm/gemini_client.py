from __future__ import annotations

from typing import Any

from quickdraw.llm.base import LLMClient
from quickdraw.llm.text_fallback import messages_to_plain_text
from quickdraw.llm.types import LLMResponse


class GeminiClient(LLMClient):
    """Text-only Gemini client (no tools yet)."""

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def name(self) -> str:
        return "gemini"

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
        transcript = "\n\n".join([f"{m['role']}: {m['content']}" for m in plain])
        prompt = (system.strip() + "\n\n" if system else "") + transcript

        try:
            resp = self._client.models.generate_content(
                model=model,
                contents=prompt,
            )
        except Exception as e:
            return LLMResponse(stop_reason="error", content=[], error=str(e))

        text = (getattr(resp, "text", None) or "").strip()
        return LLMResponse(stop_reason="end_turn", content=[{"type": "text", "text": text}])

