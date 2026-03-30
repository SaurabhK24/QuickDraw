"""Pack loader — discovers and parses MANIFEST.yaml files from pack directories."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PackAgent:
    """An agent defined within a pack."""

    id: str
    pack_id: str
    name: str
    soul_path: Path
    tools: list[str]
    model: str | None = None

    @property
    def soul(self) -> str:
        if self.soul_path.exists():
            return self.soul_path.read_text()
        return f"You are {self.name}, a helpful AI assistant."

    @property
    def qualified_id(self) -> str:
        return f"{self.pack_id}.{self.id}"


@dataclass
class WorkflowStep:
    """A single step in a multi-step workflow."""

    agent: str
    prompt_template: str = "{input}"
    requires_approval: bool = False


@dataclass
class PackWorkflowDef:
    """A workflow definition within a pack."""

    id: str
    pack_id: str
    name: str
    trigger: str
    steps: list[WorkflowStep]

    @property
    def qualified_id(self) -> str:
        return f"{self.pack_id}.{self.id}"


@dataclass
class Pack:
    """A loaded pack with all its agents and workflows."""

    id: str
    name: str
    description: str
    version: str
    directory: Path
    agents: dict[str, PackAgent]
    workflows: dict[str, PackWorkflowDef]
    router_hint: str = ""
    custom_tools: dict[str, dict[str, Any]] = field(default_factory=dict)


BUILTIN_TOOLS = {"shell", "filesystem", "memory", "web_search", "write_file", "read_file"}


def load_pack(pack_dir: Path) -> Pack | None:
    """Load a single pack from its directory."""
    manifest_path = pack_dir / "MANIFEST.yaml"
    if not manifest_path.exists():
        return None

    try:
        raw = yaml.safe_load(manifest_path.read_text())
    except Exception:
        logger.warning("Failed to parse %s", manifest_path, exc_info=True)
        return None

    pack_id = raw.get("id", pack_dir.name)
    pack_name = raw.get("name", pack_id.replace("-", " ").replace("_", " ").title())

    agents: dict[str, PackAgent] = {}
    for agent_id, agent_raw in raw.get("agents", {}).items():
        soul_file = agent_raw.get("soul", f"souls/{agent_id}.md")
        soul_path = pack_dir / soul_file
        agents[agent_id] = PackAgent(
            id=agent_id,
            pack_id=pack_id,
            name=agent_raw.get("name", agent_id.replace("_", " ").replace("-", " ").title()),
            soul_path=soul_path,
            tools=agent_raw.get("tools", ["filesystem", "web_search"]),
            model=agent_raw.get("model"),
        )

    workflows: dict[str, PackWorkflowDef] = {}
    for wf_id, wf_raw in raw.get("workflows", {}).items():
        steps = []
        for step_raw in wf_raw.get("steps", []):
            steps.append(WorkflowStep(
                agent=step_raw["agent"],
                prompt_template=step_raw.get("prompt_template", "{input}"),
                requires_approval=step_raw.get("requires_approval", False),
            ))
        workflows[wf_id] = PackWorkflowDef(
            id=wf_id,
            pack_id=pack_id,
            name=wf_raw.get("name", wf_id.replace("_", " ").replace("-", " ").title()),
            trigger=wf_raw.get("trigger", ""),
            steps=steps,
        )

    return Pack(
        id=pack_id,
        name=pack_name,
        description=raw.get("description", ""),
        version=raw.get("version", "1.0"),
        directory=pack_dir,
        agents=agents,
        workflows=workflows,
        router_hint=raw.get("router", {}).get("description", ""),
        custom_tools=raw.get("tools", {}),
    )


def discover_packs(packs_root: Path) -> dict[str, Pack]:
    """Discover all packs under the given root directory."""
    packs: dict[str, Pack] = {}

    if not packs_root.exists():
        return packs

    for child in sorted(packs_root.iterdir()):
        if child.is_dir() and (child / "MANIFEST.yaml").exists():
            pack = load_pack(child)
            if pack:
                packs[pack.id] = pack
                logger.info(
                    "Loaded pack: %s (%d agents, %d workflows)",
                    pack.id, len(pack.agents), len(pack.workflows),
                )

    return packs


def build_router_context(packs: dict[str, Pack]) -> str:
    """Build the routing context string that tells the router agent about available packs."""
    if not packs:
        return "No packs are loaded. Route everything to the default agent."

    lines = ["You route user messages to the correct vertical pack and agent.", "",
             "Available packs:", ""]

    for pack in packs.values():
        lines.append(f"## Pack: {pack.name} (id: {pack.id})")
        if pack.description:
            lines.append(f"  {pack.description}")
        if pack.router_hint:
            lines.append(f"  Route here when: {pack.router_hint}")
        lines.append("  Agents:")
        for agent in pack.agents.values():
            lines.append(f"    - {agent.qualified_id}: {agent.name}")
            lines.append(f"      Tools: {', '.join(agent.tools)}")
        if pack.workflows:
            lines.append("  Workflows:")
            for wf in pack.workflows.values():
                lines.append(f"    - {wf.qualified_id}: {wf.name}")
                if wf.trigger:
                    lines.append(f"      Trigger: {wf.trigger}")
                lines.append(f"      Steps: {' → '.join(s.agent for s in wf.steps)}")
        lines.append("")

    lines.extend([
        "## Routing rules:",
        "1. If the user's message clearly matches a pack's domain, route to the best-fit agent in that pack.",
        "2. If a workflow matches, route to the workflow instead of a single agent.",
        "3. If the message is ambiguous or general-purpose, route to 'default.main'.",
        "4. Always respond with ONLY a JSON object: {\"target\": \"pack.agent_or_workflow\", \"type\": \"agent\" or \"workflow\", \"reasoning\": \"brief reason\"}",
    ])

    return "\n".join(lines)
