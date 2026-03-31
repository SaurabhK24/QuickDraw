"""Temporal worker entry point.

Starts a Temporal worker that listens on the quickdraw-runs task queue
and executes all QuickDraw workflows and activities.

Usage:
    python -m quickdraw.workflows.worker
"""

from __future__ import annotations

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from quickdraw.workflows.activities import execute_agent_turn, resolve_workflow, route_message
from quickdraw.workflows.durable_run import DurableRunWorkflow
from quickdraw.workflows.pack_workflow import PackMultiStepWorkflow
from quickdraw.workflows.router_workflow import RouterWorkflow
from quickdraw.workflows.supervisor_workflow import SupervisorWorkflow

logger = logging.getLogger(__name__)

TASK_QUEUE = "quickdraw-runs"


async def run_worker() -> None:
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

    logger.info("Connecting to Temporal at %s", temporal_address)
    client = await Client.connect(temporal_address)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DurableRunWorkflow, PackMultiStepWorkflow, RouterWorkflow, SupervisorWorkflow],
        activities=[execute_agent_turn, resolve_workflow, route_message],
    )

    logger.info("Temporal worker started on queue=%s", TASK_QUEUE)
    await worker.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
