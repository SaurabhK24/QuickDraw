"""Thin repository layer for platform entities.

Keeps DB access behind simple async functions so the gateway and future
Go control plane use the same data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from quickdraw.platform.models import (
    AuditEvent,
    Run,
    RunStep,
    Tenant,
)


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

async def get_or_create_default_tenant(session: AsyncSession) -> Tenant:
    """Return the default dev tenant, creating it on first call."""
    stmt = select(Tenant).where(Tenant.slug == "default")
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(slug="default", name="Default Tenant")
        session.add(tenant)
        await session.flush()
    return tenant


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

async def create_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_key: str,
    agent_id: str,
    run_type: str = "interactive_run",
) -> Run:
    run = Run(
        tenant_id=tenant_id,
        session_key=session_key,
        run_type=run_type,
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def complete_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    status: str = "completed",
) -> None:
    stmt = (
        update(Run)
        .where(Run.id == run_id)
        .values(status=status, updated_at=datetime.now(timezone.utc))
    )
    await session.execute(stmt)


# ---------------------------------------------------------------------------
# RunStep
# ---------------------------------------------------------------------------

async def create_run_step(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    step_kind: str,
    ordinal: int = 0,
    payload: dict[str, Any] | None = None,
) -> RunStep:
    step = RunStep(
        run_id=run_id,
        step_kind=step_kind,
        ordinal=ordinal,
        status="completed",
        payload=payload,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    session.add(step)
    await session.flush()
    return step


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

async def record_audit_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    run_id: uuid.UUID | None = None,
    run_step_id: uuid.UUID | None = None,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        run_id=run_id,
        run_step_id=run_step_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event
