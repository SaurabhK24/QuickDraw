"""Temporal activities — the units of work executed by Python agent workers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


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


@activity.defn
async def execute_agent_turn(input: AgentRunInput) -> AgentRunOutput:
    """Execute a single agent turn using the existing QuickDraw runtime.

    This activity wraps the current AgentLoop so Temporal can schedule,
    retry, and track it as a durable unit of work.
    """
    from pathlib import Path

    from quickdraw.core.loop import AgentLoop
    from quickdraw.core.session import SessionManager
    from quickdraw.tools.registry import ToolRegistry

    activity.logger.info(
        "Agent turn: tenant=%s agent=%s session=%s",
        input.tenant_id, input.agent_id, input.session_key,
    )

    registry = ToolRegistry()

    from quickdraw.tools import filesystem, web
    filesystem.register(registry)
    web.register(registry)

    loop = AgentLoop(registry)

    workspace = Path("/app/.quickdraw") if Path("/app/.quickdraw").exists() else Path.home() / ".quickdraw"
    sessions = SessionManager(workspace / "sessions")
    messages = sessions.load(input.session_key)

    messages.append({"role": "user", "content": input.user_text})

    soul_path = workspace / "SOUL.md"
    if soul_path.exists():
        system_prompt = soul_path.read_text()
    else:
        system_prompt = f"You are {input.agent_id}, a helpful AI assistant."

    response_text, messages = await loop.run(
        messages=messages,
        system_prompt=system_prompt,
        model=input.model,
        max_tokens=input.max_tokens,
    )

    sessions.save(input.session_key, messages)

    return AgentRunOutput(
        response_text=response_text,
        run_id=input.session_key,
        step_count=len(messages),
    )
