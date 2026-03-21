"""Terminal REPL channel adapter."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)


class ReplChannel(ChannelAdapter):
    """Interactive terminal REPL for direct agent interaction."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._session_key = "repl:main"
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("REPL channel started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("REPL channel stopped")

    async def _loop(self) -> None:
        print("\nQuickDraw REPL")
        print("  Commands: /new (reset session), /quit (exit)")
        print()

        loop = asyncio.get_event_loop()

        while self._running:
            try:
                user_input = await loop.run_in_executor(None, self._read_input)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                self._running = False
                break

            if not user_input:
                continue

            if user_input.lower() in ("/quit", "/exit", "/q"):
                print("Goodbye!")
                self._running = False
                break

            if user_input.lower() == "/new":
                ts = datetime.now().strftime("%Y%m%d%H%M%S")
                self._session_key = f"repl:{ts}"
                print("  Session reset.\n")
                continue

            response_received = asyncio.Event()
            response_text = ""

            async def reply_fn(text: str) -> None:
                nonlocal response_text
                response_text = text
                response_received.set()

            try:
                await self._dispatch(self._session_key, user_input, reply_fn)
                await response_received.wait()
                print(f"\n{response_text}\n")
            except Exception as e:
                logger.error("Error: %s", e)
                print(f"\nError: {e}\n")

    def _read_input(self) -> str:
        try:
            return input("You: ").strip()
        except EOFError:
            raise
