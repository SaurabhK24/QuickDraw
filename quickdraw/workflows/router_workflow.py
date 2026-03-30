"""Router workflow — classifies user input and delegates to the right pack/agent.

This is the top-level Temporal workflow. Every message from every channel enters
here. The router uses a fast LLM call to classify the message, then either:
  1. Dispatches to a single agent turn (simple question)
  2. Kicks off a multi-step pack workflow (complex task matching a workflow trigger)
  3. Falls back to the default agent for general conversation
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
        route_message,
        resolve_workflow,
        RouteInput,
        RouteOutput,
    )

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "PermissionError"],
)


@dataclass
class RouterInput:
    tenant_id: str
    session_key: str
    user_text: str
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096
    pack_context: str = ""
    available_workflows: list | None = None


@dataclass
class RouterOutput:
    response_text: str
    routed_to: str = "default.main"
    route_type: str = "agent"
    step_count: int = 0


@workflow.defn
class RouterWorkflow:
    """Classifies and routes messages to the appropriate pack agent or workflow."""

    def __init__(self) -> None:
        self._result: RouterOutput | None = None

    @workflow.run
    async def run(self, input: RouterInput) -> RouterOutput:
        route = await workflow.execute_activity(
            route_message,
            RouteInput(
                user_text=input.user_text,
                pack_context=input.pack_context or "",
                model=input.model,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        workflow.logger.info(
            "Route decision: target=%s type=%s reason=%s",
            route.target, route.route_type, route.reasoning,
        )

        # --- supervisor: autonomous orchestration via delegation tools ---
        if route.route_type == "supervisor":
            from quickdraw.workflows.supervisor_workflow import (
                SupervisorWorkflow,
                SupervisorInput,
            )

            sup_result = await workflow.execute_child_workflow(
                SupervisorWorkflow.run,
                SupervisorInput(
                    tenant_id=input.tenant_id,
                    session_key=input.session_key,
                    user_text=input.user_text,
                    agent_id=route.target,
                    model=input.model,
                    max_tokens=input.max_tokens,
                ),
            )

            self._result = RouterOutput(
                response_text=sup_result.response_text,
                routed_to=route.target,
                route_type="supervisor",
                step_count=sup_result.step_count,
            )
            return self._result

        # --- multi-step pack workflow ---
        if route.route_type == "workflow":
            wf_def = _find_workflow(route.target, input.available_workflows or [])

            if not wf_def:
                wf_def = await workflow.execute_activity(
                    resolve_workflow,
                    route.target,
                    start_to_close_timeout=timedelta(seconds=10),
                )

            if wf_def:
                from quickdraw.workflows.pack_workflow import (
                    PackMultiStepWorkflow,
                    PackWorkflowInput,
                    WorkflowStepDef,
                )

                steps = [
                    WorkflowStepDef(
                        agent_id=s["agent"],
                        pack_id=s.get("pack_id", route.target.split(".")[0]),
                        prompt_template=s.get("prompt_template", "{input}"),
                        requires_approval=s.get("requires_approval", False),
                        model=s.get("model", input.model),
                        max_tokens=s.get("max_tokens", input.max_tokens),
                        retry_if=s.get("retry_if", ""),
                        retry_step=s.get("retry_step", -1),
                        max_retries=s.get("max_retries", 2),
                    )
                    for s in wf_def.get("steps", [])
                ]

                pack_result = await workflow.execute_child_workflow(
                    PackMultiStepWorkflow.run,
                    PackWorkflowInput(
                        tenant_id=input.tenant_id,
                        session_key=input.session_key,
                        user_text=input.user_text,
                        pack_id=route.target.split(".")[0],
                        workflow_id=wf_def.get("id", route.target),
                        steps=steps,
                        model=input.model,
                        max_tokens=input.max_tokens,
                    ),
                )

                self._result = RouterOutput(
                    response_text=pack_result.final_response,
                    routed_to=route.target,
                    route_type="workflow",
                    step_count=pack_result.total_steps,
                )
                return self._result

        # --- single agent turn ---
        result = await workflow.execute_activity(
            execute_agent_turn,
            AgentRunInput(
                tenant_id=input.tenant_id,
                session_key=input.session_key,
                agent_id=route.target,
                user_text=input.user_text,
                model=input.model,
                max_tokens=input.max_tokens,
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )

        self._result = RouterOutput(
            response_text=result.response_text,
            routed_to=route.target,
            route_type="agent",
            step_count=result.step_count,
        )
        return self._result

    @workflow.query
    def get_result(self) -> RouterOutput | None:
        return self._result


def _find_workflow(target: str, available: list[dict]) -> dict | None:
    for wf in available:
        if wf.get("qualified_id") == target or wf.get("id") == target:
            return wf
    return None
