"""Agent loop — the core LLM + tool execution cycle.

Calls the LLM, checks for tool use, executes tools, feeds results back,
and repeats until the model produces a final response or hits the turn limit.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from quickdraw.tools.registry import ToolRegistry
from quickdraw.llm.base import LLMClient
from quickdraw.llm.types import extract_text

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS = 20


class AgentLoop:
    """Runs one full agent turn: LLM call -> tool execution -> repeat."""

    def __init__(self, registry: ToolRegistry, llm: LLMClient) -> None:
        self._registry = registry
        self._llm = llm

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
            response = await asyncio.to_thread(
                lambda: self._llm.complete(
                    messages=messages,
                    system=system_prompt,
                    model=model,
                    max_tokens=max_tokens,
                    tools=tool_defs if tool_defs else None,
                )
            )

            if response.stop_reason == "error":
                error_msg = response.error or "LLM error"
                logger.error(error_msg)
                return error_msg, messages

            content = response.content

            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": content})
                return extract_text(content), messages

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})

                tool_results = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = str(block.get("name"))
                        tool_input = block.get("input") or {}
                        tool_id = str(block.get("id"))
                        logger.info("Tool: %s(%s)", tool_name, json.dumps(tool_input)[:120])
                        result = await self._registry.execute(tool_name, tool_input)
                        logger.info("  -> %s", str(result)[:150])
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": result,
                            }
                        )

                messages.append({"role": "user", "content": tool_results})
            else:
                messages.append({"role": "assistant", "content": content})
                return extract_text(content), messages

        return "(max tool turns reached)", messages
