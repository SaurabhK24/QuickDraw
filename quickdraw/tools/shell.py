"""Shell command execution tool with permission checks."""

from __future__ import annotations

import subprocess

from quickdraw.core.permissions import PermissionManager
from quickdraw.tools.registry import ToolRegistry

SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "The shell command to run"},
    },
    "required": ["command"],
}


def register(registry: ToolRegistry, permissions: PermissionManager) -> None:
    """Register the run_command tool."""

    def run_command(command: str) -> str:
        safety = permissions.check(command)

        if safety == "denied":
            return "Permission denied. This command was previously denied."

        if safety == "needs_approval":
            return (
                f"Permission denied. Command requires approval: {command}\n"
                "Use the REPL or Discord to approve this command."
            )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            return output.strip() if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as e:
            return f"Error running command: {e}"

    registry.register(
        name="run_command",
        description="Run a shell command on the host machine",
        input_schema=SCHEMA,
        handler=run_command,
    )
