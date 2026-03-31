"""Abstract base class for channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

ReplyFn = Callable[[str], Awaitable[None]]
MessageCallback = Callable[[str, str, ReplyFn], Awaitable[None]]

# (agent_id, session_key, user_text, model, max_tokens) -> dict
RunTurnCallback = Callable[[str, str, str, str, int], Awaitable[dict]]


class ChannelAdapter(ABC):
    """Base interface for all messaging channel adapters.

    Each adapter normalizes inbound messages into a common format and
    routes them through the gateway's message callback.
    """

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        self.channel_id = channel_id
        self.settings = settings
        self._on_message: MessageCallback | None = None
        self._on_run_turn: RunTurnCallback | None = None

    def set_message_callback(self, callback: MessageCallback) -> None:
        """Set the callback invoked when a message arrives.

        callback(session_key, user_text, reply_fn)
        """
        self._on_message = callback

    def set_run_turn_callback(self, callback: RunTurnCallback) -> None:
        """Set the callback for direct agent-turn execution.

        callback(agent_id, session_key, user_text, model, max_tokens) -> dict
        """
        self._on_run_turn = callback

    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect, authenticate, begin listening)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the channel."""

    async def _dispatch(self, session_key: str, text: str, reply_fn: ReplyFn) -> None:
        """Dispatch an inbound message to the gateway."""
        if self._on_message is not None:
            await self._on_message(session_key, text, reply_fn)
