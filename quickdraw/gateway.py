"""Gateway — central orchestrator that manages channels and routes messages.

The gateway is the single entry point. It:
  1. Loads configuration
  2. Instantiates enabled channels
  3. Sets up the agent loop, tools, sessions, and queue
  4. Routes inbound messages from any channel through the agent
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from quickdraw.channels.base import ChannelAdapter, ReplyFn
from quickdraw.config import Config
from quickdraw.core.loop import AgentLoop
from quickdraw.core.permissions import PermissionManager
from quickdraw.core.queue import CommandQueue, _QueueContext
from quickdraw.core.session import SessionManager
from quickdraw.tools.registry import ToolRegistry
from quickdraw.llm.anthropic_client import AnthropicClient
from quickdraw.llm.gemini_client import GeminiClient
from quickdraw.llm.openai_client import OpenAIClient
from quickdraw.llm.router import LLMRouter, ProviderSpec

logger = logging.getLogger(__name__)


class Gateway:
    """Central orchestrator — one gateway, many channels, shared agent."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.sessions = SessionManager(config.sessions_dir)
        self.queue = CommandQueue()

        self.permissions = PermissionManager(
            approvals_file=config.approvals_file,
            safe_commands=config.permissions.safe_commands,
            mode=config.permissions.mode,
        )

        self.registry = ToolRegistry()
        self._register_tools()

        self._llm = self._build_llm()
        self.loop = AgentLoop(self.registry, self._llm)
        self.channels: list[ChannelAdapter] = []

        self._router: Any = None
        self._heartbeat: Any = None
        self._compactor: Any = None

    def _build_llm(self) -> LLMRouter:
        llm_cfg = self.config.llm
        providers = llm_cfg.providers

        # If config didn't specify providers list, synthesize from legacy fields.
        if not providers:
            from quickdraw.config import LLMProviderConfig

            providers = [
                LLMProviderConfig(
                    provider=llm_cfg.provider,
                    model=llm_cfg.model,
                    max_tokens=llm_cfg.max_tokens,
                    api_key=None,
                )
            ]

        chain: list[tuple[ProviderSpec, Any]] = []
        for p in providers:
            provider = (p.provider or "anthropic").lower()
            model = p.model or llm_cfg.model
            max_tokens = p.max_tokens or llm_cfg.max_tokens

            if provider == "anthropic":
                chain.append((ProviderSpec(provider=provider, model=model, max_tokens=max_tokens), AnthropicClient()))
            elif provider == "openai":
                if not p.api_key:
                    raise ValueError("OpenAI provider requires llm.providers[].api_key")
                chain.append(
                    (ProviderSpec(provider=provider, model=model, max_tokens=max_tokens), OpenAIClient(p.api_key))
                )
            elif provider == "gemini":
                if not p.api_key:
                    raise ValueError("Gemini provider requires llm.providers[].api_key")
                chain.append(
                    (ProviderSpec(provider=provider, model=model, max_tokens=max_tokens), GeminiClient(p.api_key))
                )
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")

        return LLMRouter(chain)

    def _register_tools(self) -> None:
        """Register all built-in tools."""
        from quickdraw.tools import filesystem, memory_tools, shell, web

        shell.register(self.registry, self.permissions)
        filesystem.register(self.registry)
        memory_tools.register(self.registry, self.config.memory_dir)
        web.register(self.registry)

    def _create_channels(self) -> list[ChannelAdapter]:
        """Instantiate channel adapters from config."""
        adapters: list[ChannelAdapter] = []

        for ch_id, ch_cfg in self.config.channels.items():
            if not ch_cfg.enabled:
                continue

            adapter = self._make_adapter(ch_id, ch_cfg.settings)
            if adapter:
                adapter.set_message_callback(self._handle_message)
                adapters.append(adapter)

        return adapters

    def _make_adapter(self, kind: str, settings: dict[str, Any]) -> ChannelAdapter | None:
        if kind == "discord":
            from quickdraw.channels.discord_channel import DiscordChannel
            return DiscordChannel(kind, settings)
        elif kind == "repl":
            from quickdraw.channels.repl import ReplChannel
            return ReplChannel(kind, settings)
        elif kind == "http":
            from quickdraw.channels.http_api import HttpApiChannel
            return HttpApiChannel(kind, settings)
        elif kind == "signal":
            from quickdraw.channels.signal_channel import SignalChannel
            return SignalChannel(kind, settings)
        else:
            logger.warning("Unknown channel type: %s", kind)
            return None

    async def _handle_message(
        self, session_key: str, user_text: str, reply_fn: ReplyFn,
    ) -> None:
        """Process an inbound message from any channel."""
        from quickdraw.router import AgentRouter

        if self._router is None:
            self._router = AgentRouter(self.config.agents)

        agent_id, cleaned_text = self._router.resolve(user_text)
        agent_cfg = self.config.agents[agent_id]

        agent_session_key = f"{agent_cfg.name.lower()}:{session_key}"

        ctx = _QueueContext(self.queue, agent_session_key)
        async with ctx:
            messages = self.sessions.load(agent_session_key)

            if self._compactor:
                messages = await self._compactor.compact(agent_session_key, messages)

            messages.append({"role": "user", "content": cleaned_text})

            model = agent_cfg.model or self.config.llm.model
            system_prompt = agent_cfg.soul

            response_text, messages = await self.loop.run(
                messages=messages,
                system_prompt=system_prompt,
                model=model,
                max_tokens=self.config.llm.max_tokens,
            )

            self.sessions.save(agent_session_key, messages)

        agent_label = f"[{agent_cfg.name}] " if len(self.config.agents) > 1 else ""
        await reply_fn(f"{agent_label}{response_text}")

    async def start(self) -> None:
        """Start all enabled channels and background services."""
        self.config.ensure_dirs()

        if self.config.heartbeats:
            from quickdraw.heartbeat import HeartbeatScheduler
            self._heartbeat = HeartbeatScheduler(self.config, self)
            await self._heartbeat.start()

        if self.config.agents:
            from quickdraw.router import AgentRouter
            self._router = AgentRouter(self.config.agents)

        from quickdraw.core.compaction import Compactor
        self._compactor = Compactor(self.sessions, llm=self._llm, model=self.config.llm.model)

        self.channels = self._create_channels()
        for ch in self.channels:
            try:
                await ch.start()
                logger.info("Channel started: %s", ch.channel_id)
            except Exception as e:
                logger.error("Failed to start channel %s: %s", ch.channel_id, e)

    async def stop(self) -> None:
        """Gracefully shut down all channels and services."""
        if self._heartbeat:
            await self._heartbeat.stop()

        for ch in self.channels:
            try:
                await ch.stop()
            except Exception as e:
                logger.error("Error stopping channel %s: %s", ch.channel_id, e)

    def run(self) -> None:
        """Run the gateway (blocking). Sets up signal handlers for clean shutdown."""
        async def _run() -> None:
            await self.start()

            stop_event = asyncio.Event()
            loop = asyncio.get_event_loop()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            logger.info(
                "QuickDraw running — %d channel(s) active",
                len(self.channels),
            )

            await stop_event.wait()
            logger.info("Shutting down...")
            await self.stop()

        asyncio.run(_run())
