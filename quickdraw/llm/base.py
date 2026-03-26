from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quickdraw.llm.types import LLMResponse


class LLMClient(ABC):
    """Common interface for LLM providers.

    We use an Anthropic-like response shape because QuickDraw's agent loop already
    understands tool_use/tool_result with that schema.
    """

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports_tools(self) -> bool: ...

    @abstractmethod
    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        model: str,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        """Execute one model call."""

