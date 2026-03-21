"""Per-session async command queue.

Ensures only one message processes at a time per session key,
while different sessions run concurrently.
"""

from __future__ import annotations

import asyncio


class CommandQueue:
    """Per-session locking to prevent race conditions."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_key: str) -> asyncio.Lock:
        if session_key not in self._locks:
            self._locks[session_key] = asyncio.Lock()
        return self._locks[session_key]

    async def acquire(self, session_key: str) -> None:
        lock = self._get_lock(session_key)
        await lock.acquire()

    def release(self, session_key: str) -> None:
        lock = self._locks.get(session_key)
        if lock and lock.locked():
            lock.release()

    async def __call__(self, session_key: str):
        """Use as an async context manager: async with queue(session_key):"""
        return _QueueContext(self, session_key)


class _QueueContext:
    def __init__(self, queue: CommandQueue, session_key: str) -> None:
        self._queue = queue
        self._key = session_key

    async def __aenter__(self) -> None:
        await self._queue.acquire(self._key)

    async def __aexit__(self, *exc: object) -> None:
        self._queue.release(self._key)
