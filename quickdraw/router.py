"""Multi-agent message routing.

Routes messages to different agent configurations based on prefix commands.
Each agent has its own SOUL, session namespace, and optionally a different model.
"""

from __future__ import annotations

from quickdraw.config import AgentConfig


class AgentRouter:
    """Routes messages to the appropriate agent based on prefix commands."""

    PREFIXES = {
        "/research": "researcher",
    }

    def __init__(self, agents: dict[str, AgentConfig]) -> None:
        self._agents = agents

    def resolve(self, message: str) -> tuple[str, str]:
        """Resolve a message to (agent_id, cleaned_text).

        Checks for prefix commands like /research. Falls back to 'main'.
        """
        for prefix, agent_id in self.PREFIXES.items():
            if message.startswith(prefix + " ") and agent_id in self._agents:
                return agent_id, message[len(prefix) + 1:]
            if message == prefix and agent_id in self._agents:
                return agent_id, ""

        return "main", message

    def add_route(self, prefix: str, agent_id: str) -> None:
        """Register a custom prefix -> agent route."""
        self.PREFIXES[prefix] = agent_id
