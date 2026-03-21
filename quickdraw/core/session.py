"""JSONL-based session persistence.

Each session is a single .jsonl file where each line is one message.
Append-only by default for crash safety — at most one line is lost on crash.
"""

from __future__ import annotations

import json
from pathlib import Path


class SessionManager:
    """Manages conversation sessions stored as JSONL files."""

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_key: str) -> Path:
        safe_key = session_key.replace(":", "_").replace("/", "_")
        return self._dir / f"{safe_key}.jsonl"

    def load(self, session_key: str) -> list[dict]:
        """Load all messages from a session file."""
        path = self._path(session_key)
        messages: list[dict] = []
        if not path.exists():
            return messages
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return messages

    def append(self, session_key: str, message: dict) -> None:
        """Append a single message to the session (crash-safe)."""
        path = self._path(session_key)
        with open(path, "a") as f:
            f.write(json.dumps(message) + "\n")

    def save(self, session_key: str, messages: list[dict]) -> None:
        """Overwrite the entire session file."""
        path = self._path(session_key)
        with open(path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

    def reset(self, session_key: str) -> None:
        """Delete a session file."""
        path = self._path(session_key)
        if path.exists():
            path.unlink()

    def exists(self, session_key: str) -> bool:
        return self._path(session_key).exists()
