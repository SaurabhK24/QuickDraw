"""Web search tool (placeholder implementation)."""

from __future__ import annotations

from quickdraw.tools.registry import ToolRegistry

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query",
        },
    },
    "required": ["query"],
}


def register(registry: ToolRegistry) -> None:
    """Register the web_search tool."""

    def web_search(query: str) -> str:
        return (
            f"[Web search placeholder] Results for: {query}\n"
            "To enable real web search, configure a search API provider "
            "in your config.yaml (e.g. Tavily, SerpAPI, or Brave Search)."
        )

    registry.register(
        name="web_search",
        description="Search the web for information",
        input_schema=SCHEMA,
        handler=web_search,
    )
