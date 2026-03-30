"""Temporal activities — the units of work executed by Python agent workers.

Activities are the atomic units that Temporal schedules, retries, and tracks.
Each activity is a thin orchestration shim: it delegates actual LLM execution
to the QuickDraw gateway via HTTP (POST /run-turn). The gateway owns all
Anthropic API connections; the worker owns sequencing, retries, and approvals.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from temporalio import activity

logger = logging.getLogger(__name__)

# URL of the running quickdraw-python gateway. In Docker Compose this is
# http://quickdraw-python:5000; locally it defaults to localhost:5000.
_GATEWAY_URL = os.environ.get("QUICKDRAW_GATEWAY_URL", "http://localhost:5000")

_PACKS: dict | None = None


def _get_workspace() -> Path:
    return Path("/app/.quickdraw") if Path("/app/.quickdraw").exists() else Path.home() / ".quickdraw"


def _get_packs() -> dict:
    global _PACKS
    if _PACKS is None:
        from quickdraw.packs.loader import discover_packs
        packs_root = _get_workspace() / "packs"
        _PACKS = discover_packs(packs_root) if packs_root.exists() else {}
    return _PACKS


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
    """Execute a single agent turn by delegating to the QuickDraw gateway.

    The worker is a pure Temporal orchestrator — it does not run AgentLoop or
    call Anthropic directly. All LLM execution happens in the gateway process
    (quickdraw-python), which is reached via POST /run-turn.
    """
    activity.logger.info(
        "Agent turn: tenant=%s agent=%s session=%s → %s/run-turn",
        input.tenant_id, input.agent_id, input.session_key, _GATEWAY_URL,
    )

    payload = {
        "agent_id": input.agent_id,
        "session_key": input.session_key,
        "user_text": input.user_text,
        "model": input.model,
        "max_tokens": input.max_tokens,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_GATEWAY_URL}/run-turn",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Gateway /run-turn returned {resp.status}: {body[:200]}")
            data = await resp.json()

    return AgentRunOutput(
        response_text=data.get("response_text", ""),
        run_id=input.session_key,
        step_count=data.get("step_count", 0),
    )


@activity.defn
async def resolve_workflow(workflow_target: str) -> dict | None:
    """Resolve a workflow definition from loaded packs by its qualified ID (e.g. 'sales.lead-qualification')."""
    packs = _get_packs()

    def _serialize_wf(wf: Any) -> dict:
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
                    "retry_if": getattr(s, "retry_if", ""),
                    "retry_step": getattr(s, "retry_step", -1),
                    "max_retries": getattr(s, "max_retries", 2),
                }
                for s in wf.steps
            ],
        }

    parts = workflow_target.split(".", 1)
    if len(parts) == 2:
        pack_id, wf_id = parts
        if pack_id in packs and wf_id in packs[pack_id].workflows:
            return _serialize_wf(packs[pack_id].workflows[wf_id])

    for pack in packs.values():
        for wf in pack.workflows.values():
            if wf.id == workflow_target or wf.qualified_id == workflow_target:
                return _serialize_wf(wf)

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
