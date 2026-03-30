"""Temporal activities — the units of work executed by Python agent workers.

Activities are the atomic units that Temporal schedules, retries, and tracks.
Each activity runs in the Python worker process with full access to the runtime.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from temporalio import activity

logger = logging.getLogger(__name__)

_WORKSPACE: Path | None = None
_PACKS: dict | None = None


def _get_workspace() -> Path:
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE = Path("/app/.quickdraw") if Path("/app/.quickdraw").exists() else Path.home() / ".quickdraw"
    return _WORKSPACE


def _get_packs():
    global _PACKS
    if _PACKS is None:
        from quickdraw.packs.loader import discover_packs
        packs_root = _get_workspace() / "packs"
        _PACKS = discover_packs(packs_root) if packs_root.exists() else {}
    return _PACKS


def _build_registry_for_agent(agent_tools: list[str] | None = None):
    """Build a ToolRegistry with only the specified tools (or all if None)."""
    from quickdraw.core.permissions import PermissionManager
    from quickdraw.tools.registry import ToolRegistry

    registry = ToolRegistry()
    workspace = _get_workspace()

    all_tools = agent_tools is None
    tool_set = set(agent_tools) if agent_tools else set()

    permissions = PermissionManager(
        approvals_file=workspace / "exec-approvals.json",
        safe_commands=["ls", "cat", "echo", "date", "pwd", "whoami", "python", "node"],
        mode="record",
    )

    from quickdraw.tools import filesystem, memory_tools, shell, web

    if all_tools or tool_set & {"shell", "run_command"}:
        shell.register(registry, permissions)

    if all_tools or tool_set & {"filesystem", "read_file", "write_file", "list_directory"}:
        filesystem.register(registry)

    if all_tools or tool_set & {"memory", "memory_read", "memory_write", "memory_search"}:
        memory_tools.register(registry, workspace / "memory")

    if all_tools or tool_set & {"web", "web_search"}:
        web.register(registry)

    return registry


def _resolve_soul(agent_id: str) -> str:
    """Resolve the SOUL prompt for an agent, checking packs then default."""
    packs = _get_packs()

    if "." in agent_id:
        pack_id, local_agent_id = agent_id.split(".", 1)
        if pack_id in packs and local_agent_id in packs[pack_id].agents:
            return packs[pack_id].agents[local_agent_id].soul
    else:
        for pack in packs.values():
            if agent_id in pack.agents:
                return pack.agents[agent_id].soul

    workspace = _get_workspace()
    soul_path = workspace / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text()
    return f"You are {agent_id}, a helpful AI assistant."


def _get_agent_tools(agent_id: str) -> list[str] | None:
    """Get the tool list for a pack agent, or None for all tools."""
    packs = _get_packs()

    if "." in agent_id:
        pack_id, local_agent_id = agent_id.split(".", 1)
        if pack_id in packs and local_agent_id in packs[pack_id].agents:
            return packs[pack_id].agents[local_agent_id].tools

    for pack in packs.values():
        if agent_id in pack.agents:
            return pack.agents[agent_id].tools

    return None


async def _heartbeat_loop(main_task: asyncio.Task, interval: float = 10.0) -> None:
    """Send periodic heartbeats; cancel the main task if workflow is cancelled."""
    while True:
        await asyncio.sleep(interval)
        try:
            activity.heartbeat()
        except asyncio.CancelledError:
            main_task.cancel()
            raise


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgentRunInput:
    tenant_id: str
    session_key: str
    agent_id: str
    user_text: str
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096


@dataclass
class AgentRunOutput:
    response_text: str
    run_id: str | None = None
    step_count: int = 0


@dataclass
class RouteInput:
    user_text: str
    pack_context: str
    model: str = "claude-sonnet-4-5-20250929"


@dataclass
class RouteOutput:
    target: str = "default.main"
    route_type: str = "agent"
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@activity.defn
async def execute_agent_turn(input: AgentRunInput) -> AgentRunOutput:
    """Execute a single agent turn with pack-aware tool isolation and SOUL resolution."""
    from quickdraw.core.loop import AgentLoop
    from quickdraw.core.session import SessionManager

    activity.logger.info(
        "Agent turn: tenant=%s agent=%s session=%s",
        input.tenant_id, input.agent_id, input.session_key,
    )

    agent_tools = _get_agent_tools(input.agent_id)
    registry = _build_registry_for_agent(agent_tools)
    loop = AgentLoop(registry)

    workspace = _get_workspace()
    sessions = SessionManager(workspace / "sessions")
    messages = sessions.load(input.session_key)
    messages.append({"role": "user", "content": input.user_text})

    system_prompt = _resolve_soul(input.agent_id)

    async def _do_run():
        return await loop.run(
            messages=messages,
            system_prompt=system_prompt,
            model=input.model,
            max_tokens=input.max_tokens,
        )

    main_task = asyncio.create_task(_do_run())
    hb_task = asyncio.create_task(_heartbeat_loop(main_task, interval=10.0))
    try:
        response_text, messages = await main_task
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass

    sessions.save(input.session_key, messages)

    return AgentRunOutput(
        response_text=response_text,
        run_id=input.session_key,
        step_count=len(messages),
    )


@activity.defn
async def resolve_workflow(workflow_target: str) -> dict | None:
    """Resolve a workflow definition from loaded packs by its qualified ID (e.g. 'sales.lead-qualification')."""
    packs = _get_packs()

    parts = workflow_target.split(".", 1)
    if len(parts) == 2:
        pack_id, wf_id = parts
        if pack_id in packs and wf_id in packs[pack_id].workflows:
            wf = packs[pack_id].workflows[wf_id]
            return {
                "id": wf.id,
                "qualified_id": wf.qualified_id,
                "pack_id": wf.pack_id,
                "steps": [
                    {
                        "agent": s.agent,
                        "pack_id": wf.pack_id,
                        "prompt_template": s.prompt_template,
                        "requires_approval": s.requires_approval,
                    }
                    for s in wf.steps
                ],
            }

    for pack in packs.values():
        for wf in pack.workflows.values():
            if wf.id == workflow_target or wf.qualified_id == workflow_target:
                return {
                    "id": wf.id,
                    "qualified_id": wf.qualified_id,
                    "pack_id": wf.pack_id,
                    "steps": [
                        {
                            "agent": s.agent,
                            "pack_id": wf.pack_id,
                            "prompt_template": s.prompt_template,
                            "requires_approval": s.requires_approval,
                        }
                        for s in wf.steps
                    ],
                }

    return None


@activity.defn
async def route_message(input: RouteInput) -> RouteOutput:
    """Use a fast LLM call to classify which pack/agent should handle a message."""
    import anthropic

    activity.logger.info("Routing message: %s...", input.user_text[:80])

    system_prompt = input.pack_context

    if not system_prompt:
        from quickdraw.packs.loader import build_router_context
        packs = _get_packs()
        if packs:
            system_prompt = build_router_context(packs)
        else:
            return RouteOutput(target="default.main", route_type="agent", reasoning="no packs available")

    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=input.model,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": input.user_text}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(raw)
            return RouteOutput(
                target=parsed.get("target", "default.main"),
                route_type=parsed.get("type", "agent"),
                reasoning=parsed.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            activity.logger.warning("Router returned non-JSON: %s", raw[:200])
            return RouteOutput(target="default.main", route_type="agent", reasoning="parse failure, defaulting")

    except Exception as e:
        activity.logger.warning("Route classification failed: %s", e)
        return RouteOutput(target="default.main", route_type="agent", reasoning=f"error: {e}")
