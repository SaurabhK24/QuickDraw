# QuickDraw V2 Action Plan

## Objective

Land the first major architectural slice for QuickDraw V2 on this branch without attempting the full platform in one pass.

## Phase 1: Introduce platform data models

Actions:

1. Add a persistent data layer for `tenant`, `agent`, `workflow`, `run`, `approval`, and `audit` records.
2. Keep the current runtime working while adding new storage interfaces beside the existing JSONL session model.
3. Make `run` the new durable unit of work for business workflows.

Expected outcome:

- The codebase can represent enterprise state explicitly instead of only through chat history.

## Phase 2: Add the Go control plane skeleton

Actions:

1. Create a Go service for public API edge, auth middleware, tenant resolution, and core run APIs.
2. Add route groups for runs, approvals, agents, workflows, and health.
3. Keep Python private behind the Go service; do not expose Python workers directly.

Expected outcome:

- QuickDraw has a proper control plane boundary and a stable API surface.

## Phase 3: Introduce durable workflows

Actions:

1. Add Temporal workflow bootstrap for `durable_run`.
2. Keep `interactive_run` lightweight and lower latency.
3. Map approval waits and retries onto Temporal instead of custom in-process logic.

Expected outcome:

- Long-running enterprise work can survive crashes, deploys, and human delays.

## Phase 4: Split Python worker execution

Actions:

1. Refactor the current Python runtime so agent execution can run as a worker service.
2. Introduce execution envelopes carrying tenant, run, workflow, and capability context.
3. Emit typed run-step events instead of relying only on session writes and direct replies.

Expected outcome:

- Agent logic becomes deployable, scalable, and easier to govern.

## Phase 5: Move tools out of process

Actions:

1. Introduce a remote tool execution interface.
2. Move shell and filesystem operations behind sandbox workers first.
3. Add tool execution records, input hashes, output pointers, and retry-safe semantics.

Expected outcome:

- Risky tool execution is isolated from the control plane and agent runtime.

## Phase 6: Add approvals and policy enforcement

Actions:

1. Add capability checks per agent and per workflow.
2. Implement approval requests as durable workflow states.
3. Require policy evaluation before outbound actions and privileged tools.

Expected outcome:

- Enterprise agents become governed systems rather than prompt-only assistants.

## Phase 7: Add shared conversation and subscription primitives

Actions:

1. Introduce `conversation`, `participant`, `subscription`, `delivery_target`, and `outbound_message` models.
2. Decouple agent output from direct reply callbacks.
3. Add retryable delivery semantics for shared channels.

Expected outcome:

- QuickDraw can support shared business agents and multi-user subscriptions.

## Phase 8: Ship the first enterprise channel and pack

Actions:

1. Implement `MS Teams` as the first enterprise messaging surface.
2. Keep `HTTP API` as the canonical integration surface.
3. Ship one end-to-end `EA + Social Media` workflow pack using approvals and outbound delivery.

Expected outcome:

- The platform proves real enterprise value without waiting for the full connector roadmap.

## Commit Strategy

Prefer major commits by architectural boundary:

1. storage and core models
2. Go control plane skeleton
3. Temporal workflow bootstrap
4. Python worker split
5. sandbox tool execution
6. policy and approvals
7. shared conversations and deliveries
8. Teams channel and first workflow pack

## Guardrails

- Do not break the current local runtime until the replacement path exists.
- Do not add Mongo as a second primary data store in the first platform slice.
- Do not let enterprise channel support bypass the control plane.
- Do not keep dangerous tool execution in-process once the remote interface exists.
