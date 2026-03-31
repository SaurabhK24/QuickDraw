"""Gateway — central orchestrator that manages channels and routes messages.

The gateway is the single entry point. It:
  1. Loads configuration
  2. Instantiates enabled channels
  3. Discovers packs (vertical agent configurations)
  4. Routes inbound messages through Temporal (durable) or AgentLoop (fallback)
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
import uuid
from pathlib import Path
from typing import Any

from quickdraw.channels.base import ChannelAdapter, ReplyFn
from quickdraw.config import Config
from quickdraw.core.loop import AgentLoop
from quickdraw.core.permissions import PermissionManager
from quickdraw.core.queue import CommandQueue, _QueueContext
from quickdraw.core.session import SessionManager
try:
    from quickdraw.platform import db as platform_db
except ImportError:
    platform_db = None  # type: ignore[assignment]
from quickdraw.tools.registry import ToolRegistry
from quickdraw.llm.anthropic_client import AnthropicClient
from quickdraw.llm.gemini_client import GeminiClient
from quickdraw.llm.openai_client import OpenAIClient
from quickdraw.llm.router import LLMRouter, ProviderSpec

logger = logging.getLogger(__name__)

_default_tenant_id: uuid.UUID | None = None
_temporal_client: Any = None


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

        self._packs: dict = {}
        self._pack_context: str = ""
        self._available_workflows: list[dict] = []

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
                adapter.set_run_turn_callback(self.run_turn)
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
            settings["_sessions_dir"] = str(self.config.sessions_dir)
            settings["_progress_dir"] = str(self.config.workspace / "progress")
            return HttpApiChannel(kind, settings)
        elif kind == "teams":
            from quickdraw.channels.teams_channel import TeamsChannel
            return TeamsChannel(kind, settings)
        elif kind == "signal":
            from quickdraw.channels.signal_channel import SignalChannel
            return SignalChannel(kind, settings)
        else:
            logger.warning("Unknown channel type: %s", kind)
            return None

    async def _handle_message(
        self, session_key: str, user_text: str, reply_fn: ReplyFn,
    ) -> None:
        """Process an inbound message from any channel.

        If Temporal is connected, routes through the durable RouterWorkflow.
        Otherwise falls back to direct AgentLoop execution.
        """
        global _temporal_client

        if _temporal_client is not None:
            try:
                response_text = await self._handle_via_temporal(session_key, user_text)
                await reply_fn(response_text)
                return
            except Exception:
                logger.warning("Temporal execution failed, falling back to direct", exc_info=True)

        await self._handle_direct(session_key, user_text, reply_fn)

    async def _handle_via_temporal(self, session_key: str, user_text: str) -> str:
        """Submit message through Temporal RouterWorkflow for durable execution."""
        from quickdraw.workflows.router_workflow import RouterWorkflow, RouterInput

        workflow_id = f"channel-{session_key}-{uuid.uuid4().hex[:8]}"

        wf_defs = []
        for pack in self._packs.values():
            for wf in pack.workflows.values():
                wf_defs.append({
                    "id": wf.id,
                    "qualified_id": wf.qualified_id,
                    "pack_id": wf.pack_id,
                    "steps": [
                        {
                            "agent": s.agent,
                            "pack_id": wf.pack_id,
                            "prompt_template": s.prompt_template,
                            "requires_approval": s.requires_approval,
                            "retry_if": s.retry_if,
                            "retry_step": s.retry_step,
                            "max_retries": s.max_retries,
                        }
                        for s in wf.steps
                    ],
                })

        handle = await _temporal_client.start_workflow(
            RouterWorkflow.run,
            RouterInput(
                tenant_id=str(_default_tenant_id or "default"),
                session_key=session_key,
                user_text=user_text,
                model=self.config.llm.model,
                max_tokens=self.config.llm.max_tokens,
                pack_context=self._pack_context,
                available_workflows=wf_defs,
            ),
            id=workflow_id,
            task_queue="quickdraw-runs",
        )

        logger.info("Submitted to Temporal: workflow_id=%s", workflow_id)
        result = await handle.result()
        return result.response_text

    async def run_turn(
        self,
        agent_id: str,
        session_key: str,
        user_text: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        _delegation_depth: int = 0,
        _workflow_key: str = "",
    ) -> dict:
        """Execute one agent turn and return the result.

        This is the single authoritative execution path for all agent runs —
        used by both the HTTP channel's /run-turn endpoint (called by the
        Temporal worker) and the direct fallback path. The worker acts as a
        pure orchestrator; all LLM calls happen here in the gateway.

        The ``_delegation_depth`` and ``_workflow_key`` params are used by the
        swarm delegation system to track recursion depth and scope shared memory.
        """
        from quickdraw.core.loop import AgentLoop
        from quickdraw.core.session import SessionManager
        from quickdraw.packs.loader import load_custom_tools
        from quickdraw.tools.registry import ToolRegistry
        from quickdraw.tools import filesystem, memory_tools, shell, web

        workflow_key = _workflow_key or session_key

        # --- resolve agent config ---
        agent_tools: list[str] | None = None
        soul: str = f"You are {agent_id}, a helpful AI assistant."

        if "." in agent_id:
            pack_id, local_id = agent_id.split(".", 1)
            pack = self._packs.get(pack_id)
            if pack and local_id in pack.agents:
                pa = pack.agents[local_id]
                agent_tools = pa.tools
                soul = pa.soul

        tool_set = set(agent_tools) if agent_tools is not None else None

        # --- build per-turn tool registry ---
        registry = ToolRegistry()

        if tool_set is None or tool_set & {"shell", "run_command"}:
            shell.register(registry, self.permissions)
        if tool_set is None or tool_set & {"filesystem", "read_file", "write_file", "list_directory"}:
            filesystem.register(registry)
        if tool_set is None or tool_set & {"memory", "memory_read", "memory_write", "memory_search"}:
            memory_tools.register(registry, self.config.memory_dir)
        if tool_set is None or tool_set & {"web", "web_search"}:
            web.register(registry)

        # --- swarm: delegation tools ---
        _DELEGATION_TOOLS = {
            "delegate_to_agent", "list_available_agents",
            "delegate_parallel", "delegate",
        }
        if tool_set is None or tool_set & _DELEGATION_TOOLS:
            from quickdraw.tools import delegate

            progress_fn = self._make_progress_fn(workflow_key)
            delegate.register(
                registry,
                run_turn_fn=self.run_turn,
                available_agents=self._build_agent_catalog(exclude=agent_id),
                workflow_key=workflow_key,
                depth=_delegation_depth,
                progress_fn=progress_fn,
            )

        # --- swarm: shared workflow memory ---
        _SHARED_MEM_TOOLS = {
            "shared_memory_write", "shared_memory_read",
            "shared_memory_list", "shared_memory",
        }
        in_delegation = bool(_workflow_key) or _delegation_depth > 0
        if in_delegation or tool_set is None or tool_set & _SHARED_MEM_TOOLS:
            from quickdraw.tools import swarm_memory
            swarm_memory.register(
                registry,
                memory_dir=self.config.memory_dir,
                namespace=workflow_key,
            )

        # --- pack custom tools ---
        if "." in agent_id:
            pack_id = agent_id.split(".", 1)[0]
            pack = self._packs.get(pack_id)
            if pack:
                for tool_def in load_custom_tools(pack):
                    if tool_set is None or tool_def["name"] in tool_set:
                        registry.register(
                            name=tool_def["name"],
                            description=tool_def["description"],
                            input_schema=tool_def["input_schema"],
                            handler=tool_def["handler"],
                        )

        # --- run the agent turn ---
        loop = AgentLoop(registry, self._llm)
        sessions = SessionManager(self.config.sessions_dir)
        messages = sessions.load(session_key)
        messages.append({"role": "user", "content": user_text})

        response_text, messages = await loop.run(
            messages=messages,
            system_prompt=soul,
            model=model,
            max_tokens=max_tokens,
        )

        sessions.save(session_key, messages)

        return {"response_text": response_text, "step_count": len(messages)}

    def _make_progress_fn(self, workflow_key: str):
        """Create a progress callback that writes events to a JSONL file."""
        progress_dir = self.config.workspace / "progress"
        safe_key = workflow_key.replace(":", "_").replace("/", "_")
        path = progress_dir / f"{safe_key}.jsonl"

        async def _write(event: dict) -> None:
            event.setdefault("ts", time.time())
            progress_dir.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(event) + "\n")

        return _write

    def _build_agent_catalog(self, exclude: str = "") -> list[dict]:
        """Build a catalog of all agents across loaded packs for delegation."""
        catalog: list[dict] = []
        for pack in self._packs.values():
            for agent in pack.agents.values():
                qid = agent.qualified_id
                if qid == exclude:
                    continue
                soul_preview = ""
                try:
                    raw = agent.soul
                    for line in raw.splitlines():
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            soul_preview = stripped[:140]
                            break
                except Exception:
                    pass
                catalog.append({
                    "id": qid,
                    "name": agent.name,
                    "pack": pack.name,
                    "description": soul_preview,
                    "tools": agent.tools,
                })
        return catalog

    async def _handle_direct(
        self, session_key: str, user_text: str, reply_fn: ReplyFn,
    ) -> None:
        """Fallback: run directly through AgentLoop without Temporal."""
        from quickdraw.router import AgentRouter

        if self._router is None:
            self._router = AgentRouter(self.config.agents)

        agent_id, cleaned_text = self._router.resolve(user_text)
        agent_cfg = self.config.agents[agent_id]

        agent_session_key = f"{agent_cfg.name.lower()}:{session_key}"

        run_id: uuid.UUID | None = None
        tenant_id = _default_tenant_id

        if platform_db and platform_db.is_available() and tenant_id is not None:
            run_id = await self._record_run_start(tenant_id, agent_session_key, agent_id)

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

        if platform_db and platform_db.is_available() and run_id is not None and tenant_id is not None:
            await self._record_run_end(tenant_id, run_id, response_text)

        agent_label = f"[{agent_cfg.name}] " if len(self.config.agents) > 1 else ""
        await reply_fn(f"{agent_label}{response_text}")

    # ------------------------------------------------------------------
    # Platform dual-write helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _record_run_start(
        tenant_id: uuid.UUID, session_key: str, agent_id: str,
    ) -> uuid.UUID | None:
        from quickdraw.platform.repositories import create_run, record_audit_event

        try:
            async with platform_db.get_session() as session:
                run = await create_run(
                    session,
                    tenant_id=tenant_id,
                    session_key=session_key,
                    agent_id=agent_id,
                )
                await record_audit_event(
                    session,
                    tenant_id=tenant_id,
                    event_type="run.started",
                    run_id=run.id,
                    payload={"session_key": session_key, "agent_id": agent_id},
                )
                return run.id
        except Exception:
            logger.warning("Platform: failed to record run start", exc_info=True)
            return None

    @staticmethod
    async def _record_run_end(
        tenant_id: uuid.UUID, run_id: uuid.UUID, response_text: str,
    ) -> None:
        from quickdraw.platform.repositories import (
            complete_run,
            create_run_step,
            record_audit_event,
        )

        try:
            async with platform_db.get_session() as session:
                await create_run_step(
                    session,
                    run_id=run_id,
                    step_kind="model_response",
                    payload={"response_preview": response_text[:500]},
                )
                await complete_run(session, run_id, status="completed")
                await record_audit_event(
                    session,
                    tenant_id=tenant_id,
                    event_type="run.completed",
                    run_id=run_id,
                )
        except Exception:
            logger.warning("Platform: failed to record run end", exc_info=True)

    async def start(self) -> None:
        """Start all enabled channels and background services."""
        global _default_tenant_id, _temporal_client

        self.config.ensure_dirs()

        if self.config.database_url and platform_db:
            await platform_db.init_db(self.config.database_url)
            from quickdraw.platform.repositories import get_or_create_default_tenant
            async with platform_db.get_session() as session:
                tenant = await get_or_create_default_tenant(session)
                _default_tenant_id = tenant.id
            logger.info("Platform DB ready — tenant=%s", _default_tenant_id)

        temporal_addr = self.config.temporal_address
        if temporal_addr:
            try:
                from temporalio.client import Client
                _temporal_client = await Client.connect(temporal_addr)
                logger.info("Temporal client connected — %s", temporal_addr)
            except Exception:
                logger.warning("Temporal connection failed", exc_info=True)
                _temporal_client = None

        self._load_packs()

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

    def _load_packs(self) -> None:
        """Discover and load all agent packs."""
        from quickdraw.packs.loader import discover_packs, build_router_context

        packs_dir = self.config.workspace / "packs"
        self._packs = discover_packs(packs_dir)

        if self._packs:
            self._pack_context = build_router_context(self._packs)
            logger.info("Loaded %d packs: %s", len(self._packs), list(self._packs.keys()))

            self._available_workflows = []
            for pack in self._packs.values():
                for wf in pack.workflows.values():
                    self._available_workflows.append({
                        "id": wf.id,
                        "qualified_id": wf.qualified_id,
                        "pack_id": wf.pack_id,
                        "name": wf.name,
                    })
        else:
            logger.info("No packs found at %s — using default agent only", packs_dir)

    async def stop(self) -> None:
        """Gracefully shut down all channels and services."""
        if self._heartbeat:
            await self._heartbeat.stop()

        for ch in self.channels:
            try:
                await ch.stop()
            except Exception as e:
                logger.error("Error stopping channel %s: %s", ch.channel_id, e)

        if platform_db:
            await platform_db.close_db()

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
