"""File-based long-term memory store.

Memories are stored as individual markdown files in the workspace memory
directory. Keyword search scans all files for matching terms.

Future enhancement: vector search with embeddings for semantic matching.
"""

from __future__ import annotations

from pathlib import Path


class MemoryStore:
    """Persistent memory store backed by markdown files."""

    def __init__(self, memory_dir: Path) -> None:
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, content: str) -> str:
        """Save or overwrite a memory entry."""
        safe_key = key.replace("/", "_").replace(" ", "-")
        filepath = self._dir / f"{safe_key}.md"
        filepath.write_text(content)
        return f"Saved to memory: {key}"

    def load(self, key: str) -> str | None:
        """Load a specific memory entry by key."""
        safe_key = key.replace("/", "_").replace(" ", "-")
        filepath = self._dir / f"{safe_key}.md"
        if filepath.exists():
            return filepath.read_text()
        return None

    def search(self, query: str) -> list[tuple[str, str]]:
        """Search memories by keyword matching.

        Returns list of (filename, content) tuples for matching files.
        """
        if not self._dir.exists():
            return []

        query_words = query.lower().split()
        results: list[tuple[str, str]] = []

        for fpath in sorted(self._dir.glob("*.md")):
            content = fpath.read_text()
            if any(word in content.lower() for word in query_words):
                results.append((fpath.stem, content))

        return results

    def list_keys(self) -> list[str]:
        """List all memory keys."""
        if not self._dir.exists():
            return []
        return [f.stem for f in sorted(self._dir.glob("*.md"))]

    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        safe_key = key.replace("/", "_").replace(" ", "-")
        filepath = self._dir / f"{safe_key}.md"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
