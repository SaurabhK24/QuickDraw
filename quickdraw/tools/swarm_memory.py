"""Workflow-scoped shared memory — allows agents in a delegation chain to share context.

Unlike the personal ``save_memory`` / ``memory_search`` tools (which are
per-agent, long-term), shared memory is scoped to a single workflow / chat
session and is readable by every agent in the delegation chain.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from quickdraw.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

WRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {
            "type": "string",
            "description": "Key to store data under (e.g. 'analysis-results', 'compliance-gaps').",
        },
        "value": {
            "type": "string",
            "description": "The data to store. Other agents in this workflow can read it.",
        },
    },
    "required": ["key", "value"],
}

READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {
            "type": "string",
            "description": "Key to retrieve from shared workflow memory.",
        },
    },
    "required": ["key"],
}

LIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}


def register(registry: ToolRegistry, memory_dir: Path, namespace: str) -> None:
    """Register workflow-scoped shared memory tools.

    All agents delegated within the same *namespace* (typically the chat
    session key) can read and write to the same shared memory.
    """
    safe_ns = namespace.replace(":", "_").replace("/", "_")
    ns_dir = memory_dir / "shared" / safe_ns

    def shared_memory_write(key: str, value: str) -> str:
        ns_dir.mkdir(parents=True, exist_ok=True)
        (ns_dir / f"{key}.md").write_text(value)
        return f"Stored '{key}' in shared workflow memory ({len(value)} chars)."

    def shared_memory_read(key: str) -> str:
        path = ns_dir / f"{key}.md"
        if not path.exists():
            available = [p.stem for p in ns_dir.glob("*.md")] if ns_dir.exists() else []
            hint = f" Available keys: {', '.join(available)}" if available else ""
            return f"No data found for key '{key}'.{hint}"
        return path.read_text()

    def shared_memory_list() -> str:
        if not ns_dir.exists():
            return "Shared workflow memory is empty."
        keys = sorted(p.stem for p in ns_dir.glob("*.md"))
        if not keys:
            return "Shared workflow memory is empty."
        entries = []
        for k in keys:
            size = (ns_dir / f"{k}.md").stat().st_size
            entries.append(f"  • {k}  ({size:,} bytes)")
        return f"Shared memory keys ({len(keys)}):\n" + "\n".join(entries)

    registry.register(
        name="shared_memory_write",
        description=(
            "Write data to shared workflow memory. All agents in this "
            "delegation chain can read it. Use to pass large context, "
            "intermediate results, or coordination signals between agents."
        ),
        input_schema=WRITE_SCHEMA,
        handler=shared_memory_write,
    )
    registry.register(
        name="shared_memory_read",
        description=(
            "Read data from shared workflow memory written by any agent "
            "in this delegation chain."
        ),
        input_schema=READ_SCHEMA,
        handler=shared_memory_read,
    )
    registry.register(
        name="shared_memory_list",
        description="List all keys stored in shared workflow memory for this workflow.",
        input_schema=LIST_SCHEMA,
        handler=shared_memory_list,
    )
