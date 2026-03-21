"""Command permission controls.

Three modes:
  - ask:    prompt the user for approval on unknown commands
  - record: allow but log the command for review
  - ignore: allow everything silently
"""

from __future__ import annotations

import json
from pathlib import Path


class PermissionManager:
    """Manages command execution permissions with a persistent allowlist."""

    def __init__(
        self,
        approvals_file: Path,
        safe_commands: list[str] | None = None,
        mode: str = "ask",
    ) -> None:
        self._file = approvals_file
        self._safe = set(safe_commands or [])
        self._mode = mode
        self._approvals: dict[str, list[str]] | None = None

    def _load(self) -> dict[str, list[str]]:
        if self._approvals is not None:
            return self._approvals
        if self._file.exists():
            with open(self._file) as f:
                self._approvals = json.load(f)
        else:
            self._approvals = {"allowed": [], "denied": []}
        return self._approvals

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w") as f:
            json.dump(self._approvals, f, indent=2)

    def check(self, command: str) -> str:
        """Check command safety. Returns 'safe', 'approved', 'denied', or 'needs_approval'."""
        if self._mode == "ignore":
            return "safe"

        base_cmd = command.strip().split()[0] if command.strip() else ""
        if base_cmd in self._safe:
            return "safe"

        approvals = self._load()
        if command in approvals["allowed"]:
            return "approved"
        if command in approvals["denied"]:
            return "denied"

        if self._mode == "record":
            self.record_approval(command, approved=True)
            return "approved"

        return "needs_approval"

    def record_approval(self, command: str, *, approved: bool) -> None:
        """Record a user's approval or denial decision."""
        data = self._load()
        key = "allowed" if approved else "denied"
        if command not in data[key]:
            data[key].append(command)
            self._save()

    @property
    def mode(self) -> str:
        return self._mode
