from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


StopReason = Literal["end_turn", "tool_use", "error"]


@dataclass
class LLMResponse:
    stop_reason: StopReason
    # Content is a list of Anthropic-like blocks: {"type":"text","text":...} or {"type":"tool_use",...}
    content: list[dict[str, Any]]
    # Optional error string for stop_reason="error"
    error: str | None = None


def extract_text(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in content:
        if block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)

