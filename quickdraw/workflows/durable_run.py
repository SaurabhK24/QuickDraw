"""Temporal workflow definition for durable agent runs.

A durable run is the enterprise alternative to an interactive chat turn.
It survives crashes, supports retries, and can pause for human approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from quickdraw.workflows.activities import (
        AgentRunInput,
        AgentRunOutput,
        execute_agent_turn,
    )


@dataclass
class DurableRunInput:
    tenant_id: str
    session_key: str
    agent_id: str
    user_text: str
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096
    requires_approval: bool = False


@workflow.defn
class DurableRunWorkflow:
    """A durable agent run backed by Temporal.

    Execution flow:
      1. Execute the agent turn as an activity.
      2. If approval is required, pause and wait for a signal.
      3. Record completion.
    """

    def __init__(self) -> None:
        self._approved: bool | None = None
        self._result: AgentRunOutput | None = None

    @workflow.run
    async def run(self, input: DurableRunInput) -> AgentRunOutput:
        result = await workflow.execute_activity(
            execute_agent_turn,
            AgentRunInput(
                tenant_id=input.tenant_id,
                session_key=input.session_key,
                agent_id=input.agent_id,
                user_text=input.user_text,
                model=input.model,
                max_tokens=input.max_tokens,
            ),
            start_to_close_timeout=timedelta(minutes=5),
        )

        self._result = result

        if input.requires_approval:
            workflow.logger.info("Waiting for approval signal")
            await workflow.wait_condition(lambda: self._approved is not None)

            if not self._approved:
                return AgentRunOutput(
                    response_text="[Run rejected by approver]",
                    run_id=result.run_id,
                )

        return result

    @workflow.signal
    async def approve(self, approved: bool) -> None:
        self._approved = approved

    @workflow.query
    def get_result(self) -> AgentRunOutput | None:
        return self._result
