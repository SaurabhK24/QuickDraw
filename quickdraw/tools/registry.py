"""Tool registration and discovery.

Tools register with a schema and a handler function. The registry
provides definitions in Anthropic's tool format and dispatches execution.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


class ToolRegistry:
    """Registry of available tools for the agent loop."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a tool with its schema and handler."""
        self._tools[name] = ToolDef(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    async def execute(self, name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name, returning the result as a string."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**tool_input)
            else:
                result = await asyncio.to_thread(tool.handler, **tool_input)
            return str(result)
        except Exception as e:
            return f"Tool error ({name}): {e}"

    def definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions in Anthropic API format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
