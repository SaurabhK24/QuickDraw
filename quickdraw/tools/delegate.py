"""Agent delegation tools — the core primitive for swarm orchestration.

These tools allow any agent to delegate work to specialist agents,
enabling emergent self-orchestration without hard-coded pipelines.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from quickdraw.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

RunTurnFn = Callable[..., Awaitable[dict]]
ProgressFn = Callable[[dict], Awaitable[None]]

DELEGATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "agent_id": {
            "type": "string",
            "description": (
                "Fully qualified agent ID (e.g. 'govcon.proposal-writer', "
                "'sales.lead-qualifier'). Call list_available_agents first "
                "to see what's available."
            ),
        },
        "task": {
            "type": "string",
            "description": "Clear, specific instructions for the specialist agent.",
        },
        "context": {
            "type": "string",
            "description": "Additional context, data, or prior results the agent needs.",
            "default": "",
        },
    },
    "required": ["agent_id", "task"],
}

DELEGATE_PARALLEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "delegations": {
            "type": "array",
            "description": "List of independent tasks to run in parallel across different specialists.",
            "items": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Fully qualified agent ID.",
                    },
                    "task": {
                        "type": "string",
                        "description": "Task instructions for this agent.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context for this agent.",
                        "default": "",
                    },
                },
                "required": ["agent_id", "task"],
            },
        },
    },
    "required": ["delegations"],
}

LIST_AGENTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}


async def _noop_progress(_event: dict) -> None:
    pass


def register(
    registry: ToolRegistry,
    run_turn_fn: RunTurnFn,
    available_agents: list[dict],
    workflow_key: str,
    depth: int = 0,
    max_depth: int = 4,
    progress_fn: ProgressFn | None = None,
) -> None:
    """Register delegation, parallel delegation, and agent-discovery tools."""

    _progress = progress_fn or _noop_progress
    agent_names = {a["id"]: a["name"] for a in available_agents}

    agents_text = "\n".join(
        f"  • {a['id']}  —  {a['name']} ({a.get('pack', '?')})\n"
        f"    Tools: {', '.join(a.get('tools', []))}\n"
        f"    {a.get('description', '')[:120]}"
        for a in available_agents
    )

    # ------------------------------------------------------------------
    # delegate_to_agent  (sequential, one at a time)
    # ------------------------------------------------------------------

    async def delegate_to_agent(
        agent_id: str, task: str, context: str = "",
    ) -> str:
        if depth >= max_depth:
            return (
                f"[Delegation blocked — max depth {max_depth} reached. "
                "Handle this task directly with the information you already have.]"
            )

        full_prompt = f"{task}\n\n---\nContext:\n{context}" if context else task
        delegate_session = f"{workflow_key}:delegate:{agent_id}:{depth + 1}"

        await _progress({
            "type": "delegation_start",
            "agent_id": agent_id,
            "agent_name": agent_names.get(agent_id, agent_id),
            "task_preview": task[:120],
            "parallel": False,
            "depth": depth + 1,
            "ts": time.time(),
        })

        logger.info(
            "SWARM delegate depth=%d → %s : %s…",
            depth + 1, agent_id, task[:80],
        )

        try:
            result = await run_turn_fn(
                agent_id=agent_id,
                session_key=delegate_session,
                user_text=full_prompt,
                _delegation_depth=depth + 1,
                _workflow_key=workflow_key,
            )
            response = result.get("response_text", "")

            await _progress({
                "type": "delegation_end",
                "agent_id": agent_id,
                "agent_name": agent_names.get(agent_id, agent_id),
                "response_preview": response[:200],
                "parallel": False,
                "depth": depth + 1,
                "ts": time.time(),
            })

            return response or "[Agent returned empty response]"
        except Exception as e:
            logger.exception("Delegation to %s failed", agent_id)
            await _progress({
                "type": "delegation_error",
                "agent_id": agent_id,
                "agent_name": agent_names.get(agent_id, agent_id),
                "error": str(e),
                "ts": time.time(),
            })
            return f"[Delegation to {agent_id} failed: {e}]"

    # ------------------------------------------------------------------
    # delegate_parallel  (concurrent fan-out)
    # ------------------------------------------------------------------

    async def delegate_parallel(delegations: list) -> str:
        if depth >= max_depth:
            return "[Delegation blocked — max depth reached.]"

        if not delegations:
            return "[No delegations provided.]"

        ids = [d["agent_id"] for d in delegations]

        await _progress({
            "type": "parallel_start",
            "agent_ids": ids,
            "agent_names": [agent_names.get(i, i) for i in ids],
            "count": len(delegations),
            "ts": time.time(),
        })

        async def _run_one(d: dict) -> dict:
            agent_id = d["agent_id"]
            task_text = d["task"]
            ctx = d.get("context", "")
            full_prompt = f"{task_text}\n\n---\nContext:\n{ctx}" if ctx else task_text
            session = f"{workflow_key}:delegate:{agent_id}:{depth + 1}"

            await _progress({
                "type": "delegation_start",
                "agent_id": agent_id,
                "agent_name": agent_names.get(agent_id, agent_id),
                "task_preview": task_text[:120],
                "parallel": True,
                "depth": depth + 1,
                "ts": time.time(),
            })

            try:
                result = await run_turn_fn(
                    agent_id=agent_id,
                    session_key=session,
                    user_text=full_prompt,
                    _delegation_depth=depth + 1,
                    _workflow_key=workflow_key,
                )
                text = result.get("response_text", "")
                await _progress({
                    "type": "delegation_end",
                    "agent_id": agent_id,
                    "agent_name": agent_names.get(agent_id, agent_id),
                    "response_preview": text[:200],
                    "parallel": True,
                    "depth": depth + 1,
                    "ts": time.time(),
                })
                return {"agent_id": agent_id, "response_text": text}
            except Exception as e:
                logger.exception("Parallel delegation to %s failed", agent_id)
                await _progress({
                    "type": "delegation_error",
                    "agent_id": agent_id,
                    "error": str(e),
                    "ts": time.time(),
                })
                return {"agent_id": agent_id, "response_text": f"[Error: {e}]"}

        sem = asyncio.Semaphore(4)

        async def _guarded(d: dict) -> dict:
            async with sem:
                return await _run_one(d)

        results = await asyncio.gather(*[_guarded(d) for d in delegations])

        await _progress({
            "type": "parallel_end",
            "count": len(results),
            "ts": time.time(),
        })

        parts = []
        for r in results:
            parts.append(f"## {r['agent_id']}\n\n{r['response_text']}")
        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # list_available_agents
    # ------------------------------------------------------------------

    async def list_available_agents() -> str:
        header = (
            f"Available specialist agents ({len(available_agents)} total):\n"
            f"Current delegation depth: {depth}/{max_depth}\n\n"
        )
        return header + agents_text

    # ------------------------------------------------------------------
    # Register all tools
    # ------------------------------------------------------------------

    registry.register(
        name="delegate_to_agent",
        description=(
            "Delegate a task to a specialist agent and get their response. "
            "The specialist will execute the task using their domain expertise "
            "and tools, then return their output. Use this to break complex "
            "tasks into focused sub-tasks handled by the best-fit specialist."
        ),
        input_schema=DELEGATE_SCHEMA,
        handler=delegate_to_agent,
    )

    registry.register(
        name="delegate_parallel",
        description=(
            "Run multiple delegations concurrently. Use when you have 2-4 "
            "independent sub-tasks that don't depend on each other's output. "
            "Much faster than sequential delegation for independent work."
        ),
        input_schema=DELEGATE_PARALLEL_SCHEMA,
        handler=delegate_parallel,
    )

    registry.register(
        name="list_available_agents",
        description=(
            "List all specialist agents available for delegation, including "
            "their capabilities and tools. ALWAYS call this before delegating."
        ),
        input_schema=LIST_AGENTS_SCHEMA,
        handler=list_available_agents,
    )
