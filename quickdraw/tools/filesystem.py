"""File system tools — read and write files."""

from __future__ import annotations

from pathlib import Path

from quickdraw.tools.registry import ToolRegistry

READ_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the file to read"},
    },
    "required": ["path"],
}

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the file to write"},
        "content": {"type": "string", "description": "Content to write to the file"},
    },
    "required": ["path", "content"],
}

MAX_READ_BYTES = 50_000


def register(registry: ToolRegistry) -> None:
    """Register read_file and write_file tools."""

    def read_file(path: str) -> str:
        try:
            p = Path(path).expanduser()
            content = p.read_text()
            if len(content) > MAX_READ_BYTES:
                return content[:MAX_READ_BYTES] + f"\n\n... (truncated, {len(content)} bytes total)"
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(path: str, content: str) -> str:
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    registry.register(
        name="read_file",
        description="Read a file from the filesystem",
        input_schema=READ_SCHEMA,
        handler=read_file,
    )
    registry.register(
        name="write_file",
        description="Write content to a file (creates directories if needed)",
        input_schema=WRITE_SCHEMA,
        handler=write_file,
    )
