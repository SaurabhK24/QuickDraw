"""Multi-step pack workflow — chains agent turns with context passing.

Each step in a pack workflow runs as a separate Temporal activity,
giving us per-step retries, observability, and approval gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "PermissionError"],
)


@dataclass
class WorkflowStepDef:
    agent_id: str
    pack_id: str
    prompt_template: str = "{input}"
    requires_approval: bool = False
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096
    retry_if: str = ""
    retry_step: int = -1
    max_retries: int = 2


@dataclass
class PackWorkflowInput:
    tenant_id: str
    session_key: str
    user_text: str
    pack_id: str
    workflow_id: str
    steps: list[WorkflowStepDef] = field(default_factory=list)
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096


@dataclass
class StepResult:
    step_index: int
    agent_id: str
    response_text: str
    step_count: int = 0


@dataclass
class PackWorkflowOutput:
    final_response: str
    step_results: list[StepResult] = field(default_factory=list)
    total_steps: int = 0
    status: str = "completed"


@workflow.defn
class PackMultiStepWorkflow:
    """Executes a multi-step pack workflow, chaining agent turns.

    Each step gets the previous step's output injected via prompt_template.
    Steps can require approval, which pauses the workflow until signaled.
    """

    def __init__(self) -> None:
        self._step_approvals: dict[int, bool | None] = {}
        self._step_results: list[StepResult] = []
        self._status: str = "running"

    @workflow.run
    async def run(self, input: PackWorkflowInput) -> PackWorkflowOutput:
        prev_output = input.user_text
        retry_counts: dict[int, int] = {}

        i = 0
        while i < len(input.steps):
            step = input.steps[i]
            prompt = step.prompt_template.format(
                input=prev_output,
                original_input=input.user_text,
                step_index=i,
            )

            iteration = retry_counts.get(i, 0)
            session_key = (
                f"{input.session_key}:{input.workflow_id}:step-{i}"
                + (f":retry-{iteration}" if iteration > 0 else "")
            )

            workflow.logger.info(
                "Step %d/%d (iter %d): agent=%s.%s",
                i + 1, len(input.steps), iteration,
                step.pack_id, step.agent_id,
            )

            result = await workflow.execute_activity(
                execute_agent_turn,
                AgentRunInput(
                    tenant_id=input.tenant_id,
                    session_key=session_key,
                    agent_id=f"{step.pack_id}.{step.agent_id}",
                    user_text=prompt,
                    model=step.model or input.model,
                    max_tokens=step.max_tokens or input.max_tokens,
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_RETRY,
            )

            step_result = StepResult(
                step_index=i,
                agent_id=f"{step.pack_id}.{step.agent_id}",
                response_text=result.response_text,
                step_count=result.step_count,
            )
            self._step_results.append(step_result)

            if step.requires_approval:
                self._step_approvals[i] = None
                workflow.logger.info("Step %d requires approval — pausing", i)
                await workflow.wait_condition(
                    lambda idx=i: self._step_approvals.get(idx) is not None
                )

                if not self._step_approvals[i]:
                    self._status = "rejected"
                    return PackWorkflowOutput(
                        final_response=f"[Workflow rejected at step {i + 1}: {step.agent_id}]",
                        step_results=self._step_results,
                        total_steps=i + 1,
                        status="rejected",
                    )

            prev_output = result.response_text

            if (
                step.retry_if
                and step.retry_if in result.response_text
                and retry_counts.get(i, 0) < step.max_retries
                and 0 <= step.retry_step < len(input.steps)
            ):
                retry_counts[i] = retry_counts.get(i, 0) + 1
                workflow.logger.info(
                    "Condition '%s' met at step %d — looping back to step %d (retry %d/%d)",
                    step.retry_if, i, step.retry_step,
                    retry_counts[i], step.max_retries,
                )
                i = step.retry_step
                continue

            i += 1

        self._status = "completed"
        return PackWorkflowOutput(
            final_response=prev_output,
            step_results=self._step_results,
            total_steps=len(self._step_results),
            status="completed",
        )

    @workflow.signal
    async def approve_step(self, step_index: int, approved: bool) -> None:
        self._step_approvals[step_index] = approved

    @workflow.query
    def get_progress(self) -> dict:
        return {
            "status": self._status,
            "completed_steps": len(self._step_results),
            "step_results": [
                {"step": r.step_index, "agent": r.agent_id, "preview": r.response_text[:200]}
                for r in self._step_results
            ],
        }
