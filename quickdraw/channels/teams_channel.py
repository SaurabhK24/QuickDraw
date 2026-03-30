"""Microsoft Teams channel adapter using Bot Framework SDK.

Runs an aiohttp server that receives incoming activities from Azure Bot Service
at POST /api/messages, routes them through the QuickDraw agent loop, and replies
back into the Teams conversation.

Requires: pip install 'quickdraw[teams]'

Configuration (in config.yaml):
    channels:
      teams:
        enabled: true
        app_id: ${MS_APP_ID}
        app_password: ${MS_APP_PASSWORD}
        port: 3978
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import web
from botbuilder.core import TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ActivityTypes, ConversationReference

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)

TEAMS_MAX_LENGTH = 28_000


def _chunk_message(text: str, limit: int = TEAMS_MAX_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


class _BotConfig:
    """Minimal config object that ConfigurationBotFrameworkAuthentication reads."""

    def __init__(self, app_id: str, app_password: str, app_type: str = "MultiTenant",
                 tenant_id: str = "") -> None:
        self.APP_ID = app_id
        self.APP_PASSWORD = app_password
        self.APP_TYPE = app_type
        self.APP_TENANTID = tenant_id


class TeamsChannel(ChannelAdapter):
    """MS Teams adapter — receives activities via Azure Bot Service webhook."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._app_id = settings.get("app_id", "")
        self._app_password = settings.get("app_password", "")
        self._port = settings.get("port", 3978)
        self._host = settings.get("host", "0.0.0.0")

        app_type = settings.get("app_type", "MultiTenant")
        tenant_id = settings.get("tenant_id", "")

        config = _BotConfig(self._app_id, self._app_password, app_type, tenant_id)
        self._adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication(config))
        self._adapter.on_turn_error = self._on_error

        self._app = web.Application(middlewares=[aiohttp_error_middleware])
        self._app.router.add_post("/api/messages", self._handle_incoming)
        self._app.router.add_get("/api/health", self._handle_health)
        self._runner: web.AppRunner | None = None

        self._conversation_refs: dict[str, ConversationReference] = {}

    async def start(self) -> None:
        if not self._app_id or not self._app_password:
            raise ValueError(
                "Teams app_id and app_password are required. "
                "Set MS_APP_ID / MS_APP_PASSWORD or add them to config."
            )
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("Teams channel listening on http://%s:%d/api/messages", self._host, self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
        logger.info("Teams channel stopped")

    async def _handle_incoming(self, request: web.Request) -> web.Response:
        return await self._adapter.process(request, self)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "channel": "teams"})

    # ------------------------------------------------------------------
    # Bot Framework activity handlers
    # ------------------------------------------------------------------

    async def on_turn(self, turn_context: TurnContext) -> None:
        """Main dispatch — route by activity type."""
        if turn_context.activity.type == ActivityTypes.message:
            await self.on_message_activity(turn_context)
        elif turn_context.activity.type == ActivityTypes.conversation_update:
            if turn_context.activity.members_added:
                await self.on_members_added_activity(
                    turn_context.activity.members_added, turn_context
                )

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        activity = turn_context.activity

        if not activity.text:
            return

        self._store_conversation_ref(activity)

        text = self._strip_mention(activity)
        session_key = self._make_session_key(activity)

        # Show typing indicator while the agent thinks
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        response_event = asyncio.Event()
        response_text = ""

        async def reply_fn(reply: str) -> None:
            nonlocal response_text
            response_text = reply
            response_event.set()

        await self._dispatch(session_key, text, reply_fn)
        await response_event.wait()

        for chunk in _chunk_message(response_text):
            await turn_context.send_activity(chunk)

    async def on_members_added_activity(self, members_added, turn_context: TurnContext) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Hello! I'm your AI assistant. Send me a message to get started."
                )

    # ------------------------------------------------------------------
    # Proactive messaging support
    # ------------------------------------------------------------------

    def _store_conversation_ref(self, activity: Activity) -> None:
        ref = TurnContext.get_conversation_reference(activity)
        key = self._make_session_key(activity)
        self._conversation_refs[key] = ref

    async def send_proactive(self, session_key: str, message: str) -> None:
        """Send a message to a conversation without a user prompt (approvals, notifications)."""
        ref = self._conversation_refs.get(session_key)
        if not ref:
            logger.warning("No conversation reference for session %s", session_key)
            return
        await self._adapter.continue_conversation(
            ref,
            lambda ctx: ctx.send_activity(message),
            self._app_id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_session_key(self, activity: Activity) -> str:
        conv_id = activity.conversation.id if activity.conversation else "unknown"
        user_id = activity.from_property.id if activity.from_property else "unknown"
        return f"teams:{conv_id}:{user_id}"

    @staticmethod
    def _strip_mention(activity: Activity) -> str:
        """Remove the bot @mention from the message text."""
        text = activity.text or ""
        if activity.entities:
            for entity in activity.entities:
                if entity.type == "mention" and hasattr(entity, "mentioned"):
                    mentioned = entity.mentioned
                    if mentioned and hasattr(mentioned, "id"):
                        if mentioned.id == activity.recipient.id:
                            mention_text = getattr(entity, "text", "")
                            if mention_text:
                                text = text.replace(mention_text, "").strip()
        return text

    @staticmethod
    async def _on_error(context: TurnContext, error: Exception) -> None:
        logger.error("Teams bot turn error: %s", error, exc_info=True)
        try:
            await context.send_activity("Something went wrong. Please try again.")
        except Exception:
            logger.error("Failed to send error message to Teams", exc_info=True)
