"""Long-term memory tools — save and search memories across sessions."""

from __future__ import annotations

from pathlib import Path

from quickdraw.tools.registry import ToolRegistry

SAVE_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {
            "type": "string",
            "description": "Short label, e.g. 'user-preferences', 'project-notes'",
        },
        "content": {
            "type": "string",
            "description": "The information to remember",
        },
    },
    "required": ["key", "content"],
}

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What to search for in memory",
        },
    },
    "required": ["query"],
}


def register(registry: ToolRegistry, memory_dir: Path) -> None:
    """Register save_memory and memory_search tools."""

    def save_memory(key: str, content: str) -> str:
        memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = memory_dir / f"{key}.md"
        filepath.write_text(content)
        return f"Saved to memory: {key}"

    def memory_search(query: str) -> str:
        if not memory_dir.exists():
            return "No memories found."

        query_words = query.lower().split()
        results: list[str] = []

        for fpath in sorted(memory_dir.glob("*.md")):
            content = fpath.read_text()
            if any(word in content.lower() for word in query_words):
                results.append(f"--- {fpath.name} ---\n{content}")

        return "\n\n".join(results) if results else "No matching memories found."

    registry.register(
        name="save_memory",
        description="Save important information to long-term memory. Use for user preferences, key facts, and anything worth remembering across sessions.",
        input_schema=SAVE_SCHEMA,
        handler=save_memory,
    )
    registry.register(
        name="memory_search",
        description="Search long-term memory for relevant information. Use at the start of conversations to recall context.",
        input_schema=SEARCH_SCHEMA,
        handler=memory_search,
    )
