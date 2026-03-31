"""Supervisor workflow — autonomous orchestration with extended timeouts.

The supervisor agent delegates to specialist agents via tools within a single
activity execution.  Because delegation chains can take significantly longer
than a single agent turn, this workflow grants a 15-minute activity timeout
(vs. the default 5 minutes) and supports multi-turn interaction via Temporal
signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from quickdraw.workflows.activities import (
        AgentRunInput,
        AgentRunOutput,
        execute_agent_turn,
    )

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "PermissionError"],
)


@dataclass
class SupervisorInput:
    tenant_id: str
    session_key: str
    user_text: str
    agent_id: str = "core.supervisor"
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 8192
    multi_turn: bool = False


@dataclass
class SupervisorOutput:
    response_text: str
    step_count: int = 0
    turn_count: int = 1
    status: str = "completed"


@workflow.defn
class SupervisorWorkflow:
    """Runs a supervisor agent with extended timeout and optional multi-turn.

    Single-turn (default):  execute one supervisor turn and return.
    Multi-turn:  after the first turn, wait for ``send_message`` signals
    to continue the conversation within the same Temporal workflow.
    """

    def __init__(self) -> None:
        self._result: SupervisorOutput | None = None
        self._pending_input: str | None = None
        self._turn_count = 0
        self._done = False

    @workflow.run
    async def run(self, input: SupervisorInput) -> SupervisorOutput:
        result = await self._execute_turn(input, input.user_text)
        self._turn_count = 1
        self._result = SupervisorOutput(
            response_text=result.response_text,
            step_count=result.step_count,
            turn_count=1,
        )

        if not input.multi_turn:
            return self._result

        while not self._done:
            await workflow.wait_condition(
                lambda: self._pending_input is not None or self._done
            )
            if self._done:
                break

            user_input = self._pending_input
            self._pending_input = None

            result = await self._execute_turn(input, user_input)
            self._turn_count += 1
            self._result = SupervisorOutput(
                response_text=result.response_text,
                step_count=result.step_count,
                turn_count=self._turn_count,
            )

        self._result.status = "ended"
        return self._result

    async def _execute_turn(
        self, input: SupervisorInput, user_text: str,
    ) -> AgentRunOutput:
        return await workflow.execute_activity(
            execute_agent_turn,
            AgentRunInput(
                tenant_id=input.tenant_id,
                session_key=input.session_key,
                agent_id=input.agent_id,
                user_text=user_text,
                model=input.model,
                max_tokens=input.max_tokens,
            ),
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_RETRY,
        )

    @workflow.signal
    async def send_message(self, message: str) -> None:
        self._pending_input = message

    @workflow.signal
    async def end_conversation(self) -> None:
        self._done = True

    @workflow.query
    def get_result(self) -> dict | None:
        if self._result is None:
            return None
        return {
            "response_text": self._result.response_text,
            "step_count": self._result.step_count,
            "turn_count": self._turn_count,
        }
