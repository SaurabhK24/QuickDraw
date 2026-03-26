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
    from quickdraw.config import AgentConfig
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

    messages: list[dict[str, Any]] = []
    messages.append({"role": "user", "content": input.user_text})

    system_prompt = f"You are {input.agent_id}, a helpful AI assistant."

    response_text, messages = await loop.run(
        messages=messages,
        system_prompt=system_prompt,
        model=input.model,
        max_tokens=input.max_tokens,
    )

    return AgentRunOutput(
        response_text=response_text,
        step_count=len(messages),
    )
