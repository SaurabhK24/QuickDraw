"""Heartbeat scheduler — runs agent tasks on a cron schedule.

Each heartbeat gets its own isolated session key so scheduled tasks
don't pollute interactive conversation history.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from croniter import croniter

if TYPE_CHECKING:
    from quickdraw.config import Config
    from quickdraw.gateway import Gateway

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Runs configured heartbeats on cron schedules."""

    def __init__(self, config: Config, gateway: Gateway) -> None:
        self._config = config
        self._gateway = gateway
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        for hb_id, hb_cfg in self._config.heartbeats.items():
            task = asyncio.create_task(
                self._run_heartbeat(hb_id, hb_cfg.schedule, hb_cfg.agent, hb_cfg.prompt),
            )
            self._tasks.append(task)
        if self._tasks:
            logger.info("Started %d heartbeat(s)", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run_heartbeat(
        self, name: str, schedule: str, agent_id: str, prompt: str,
    ) -> None:
        """Run a single heartbeat on its cron schedule."""
        cron = croniter(schedule, datetime.now(timezone.utc))

        while self._running:
            next_run = cron.get_next(datetime)
            now = datetime.now(timezone.utc)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)

            delay = (next_run - now).total_seconds()
            if delay > 0:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    return

            if not self._running:
                return

            logger.info("Heartbeat firing: %s", name)
            session_key = f"cron:{name}"

            try:
                async def noop_reply(text: str) -> None:
                    logger.info("Heartbeat [%s] response: %s", name, text[:200])

                await self._gateway._handle_message(session_key, prompt, noop_reply)
            except Exception as e:
                logger.error("Heartbeat %s failed: %s", name, e)
