"""HTTP API channel adapter using aiohttp."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiohttp import web

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)


class HttpApiChannel(ChannelAdapter):
    """HTTP API adapter exposing POST /chat for programmatic access."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._port = settings.get("port", 5000)
        self._host = settings.get("host", "127.0.0.1")
        self._app = web.Application()
        self._app.router.add_post("/chat", self._handle_chat)
        self._app.router.add_post("/run-turn", self._handle_run_turn)
        self._app.router.add_get("/health", self._handle_health)
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("HTTP API listening on http://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
        logger.info("HTTP API stopped")

    async def _handle_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        user_id = data.get("user_id")
        message = data.get("message")

        if not user_id or not message:
            return web.json_response(
                {"error": "Both 'user_id' and 'message' are required"},
                status=400,
            )

        session_key = f"http:{user_id}"

        response_event = asyncio.Event()
        response_text = ""

        async def reply_fn(text: str) -> None:
            nonlocal response_text
            response_text = text
            response_event.set()

        await self._dispatch(session_key, message, reply_fn)
        await response_event.wait()

        return web.json_response({"response": response_text})

    async def _handle_run_turn(self, request: web.Request) -> web.Response:
        """Direct agent-turn execution for Temporal workers.

        POST /run-turn
        {
            "agent_id": "govcon.proposal-analyst",
            "session_key": "session:abc",
            "user_text": "...",
            "model": "claude-sonnet-4-5-20250929",  # optional
            "max_tokens": 4096                       # optional
        }
        """
        if self._on_run_turn is None:
            return web.json_response({"error": "run-turn not configured"}, status=503)

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        agent_id = data.get("agent_id", "")
        session_key = data.get("session_key", "")
        user_text = data.get("user_text", "")

        if not agent_id or not session_key or not user_text:
            return web.json_response(
                {"error": "agent_id, session_key, and user_text are required"},
                status=400,
            )

        model = data.get("model", "claude-sonnet-4-5-20250929")
        max_tokens = int(data.get("max_tokens", 4096))

        try:
            result = await self._on_run_turn(agent_id, session_key, user_text, model, max_tokens)
            return web.json_response(result)
        except Exception as e:
            logger.exception("run-turn failed for agent=%s", agent_id)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})
