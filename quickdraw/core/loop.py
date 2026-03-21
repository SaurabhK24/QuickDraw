"""Agent loop — the core LLM + tool execution cycle.

Calls the LLM, checks for tool use, executes tools, feeds results back,
and repeats until the model produces a final response or hits the turn limit.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from quickdraw.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS = 20


def _serialize_content(content: list[Any]) -> list[dict]:
    """Convert Anthropic API content blocks to JSON-serializable dicts."""
    serialized = []
    for block in content:
        if hasattr(block, "text"):
            serialized.append({"type": "text", "text": block.text})
        elif getattr(block, "type", None) == "tool_use":
            serialized.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return serialized


class AgentLoop:
    """Runs one full agent turn: LLM call -> tool execution -> repeat."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._client = anthropic.Anthropic()

    async def run(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict]]:
        """Execute a full agent turn, returning (response_text, updated_messages).

        The messages list is mutated in place and also returned.
        """
        tool_defs = self._registry.definitions()

        for turn in range(MAX_TOOL_TURNS):
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
            }
            if tool_defs:
                kwargs["tools"] = tool_defs

            try:
                response = self._client.messages.create(**kwargs)
            except anthropic.APIError as e:
                error_msg = f"API error: {e.message}" if hasattr(e, "message") else f"API error: {e}"
                logger.error(error_msg)
                return error_msg, messages

            content = _serialize_content(response.content)

            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": content})
                text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )
                return text, messages

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        logger.info("Tool: %s(%s)", block.name, json.dumps(block.input)[:120])
                        result = await self._registry.execute(block.name, block.input)
                        logger.info("  -> %s", str(result)[:150])
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                messages.append({"role": "assistant", "content": content})
                text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )
                return text, messages

        return "(max tool turns reached)", messages
