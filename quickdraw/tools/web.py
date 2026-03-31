"""Web search tool – uses Serper.dev when SERPER_API_KEY is set."""

from __future__ import annotations

import os

import httpx

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


def _web_search(query: str) -> str:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return (
            f"[Web search placeholder] Results for: {query}\n"
            "To enable real web search, set SERPER_API_KEY environment variable.\n"
            "Get a free API key at https://serper.dev"
        )

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:5]:
            results.append(
                f"**{item.get('title', '')}**\n"
                f"{item.get('link', '')}\n"
                f"{item.get('snippet', '')}\n"
            )

        if not results:
            return f"No results found for: {query}"

        return f"Search results for: {query}\n\n" + "\n".join(results)
    except Exception as e:
        return f"Web search error: {e}\nQuery was: {query}"


def register(registry: ToolRegistry) -> None:
    """Register the web_search tool."""

    registry.register(
        name="web_search",
        description="Search the web for information",
        input_schema=SCHEMA,
        handler=_web_search,
    )
