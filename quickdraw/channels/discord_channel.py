"""Discord channel adapter using discord.py."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)

DISCORD_MAX_LENGTH = 2000


def _chunk_message(text: str, limit: int = DISCORD_MAX_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Discord's limit."""
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


class DiscordChannel(ChannelAdapter):
    """Discord adapter — listens for DMs and @mentions."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._token = settings.get("token", "")
        self._session_scope = settings.get("session_scope", "per-user")

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._ready_event = asyncio.Event()

        @self._client.event
        async def on_ready() -> None:
            logger.info("Discord connected as %s", self._client.user)
            self._ready_event.set()

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == self._client.user:
                return

            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self._client.user in message.mentions if self._client.user else False

            if not is_dm and not is_mentioned:
                return

            text = message.content
            if is_mentioned and self._client.user:
                text = text.replace(f"<@{self._client.user.id}>", "").strip()

            session_key = self._make_session_key(message)

            async def reply_fn(response: str) -> None:
                for chunk in _chunk_message(response):
                    await message.reply(chunk)

            await self._dispatch(session_key, text, reply_fn)

    def _make_session_key(self, message: discord.Message) -> str:
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)

        if self._session_scope == "per-channel-peer":
            return f"discord:{channel_id}:{user_id}"
        elif self._session_scope == "per-channel":
            return f"discord:{channel_id}"
        else:
            return f"discord:{user_id}"

    async def start(self) -> None:
        if not self._token:
            raise ValueError("Discord token not configured. Set DISCORD_BOT_TOKEN or add token to config.")
        asyncio.create_task(self._client.start(self._token))
        await self._ready_event.wait()
        logger.info("Discord channel started")

    async def stop(self) -> None:
        await self._client.close()
        logger.info("Discord channel stopped")
