"""Configuration loader with environment variable substitution."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)}")


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} references in config values."""
    if isinstance(value, str):
        def _replacer(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                raise ValueError(f"Environment variable ${{{var_name}}} is not set")
            return env_val

        return _ENV_VAR_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


@dataclass
class AgentConfig:
    name: str
    soul_path: str
    model: str | None = None

    @property
    def soul(self) -> str:
        """Load the SOUL content from the file path."""
        path = Path(self.soul_path)
        if path.exists():
            return path.read_text()
        return f"You are {self.name}, a helpful AI assistant."


@dataclass
class ChannelConfig:
    kind: str
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeartbeatConfig:
    name: str
    schedule: str
    agent: str
    prompt: str


@dataclass
class PermissionsConfig:
    mode: str = "ask"
    safe_commands: list[str] = field(default_factory=lambda: [
        "ls", "cat", "head", "tail", "wc", "date", "whoami",
        "echo", "pwd", "which", "git", "python", "node", "npm",
    ])


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 4096


@dataclass
class Config:
    workspace: Path
    llm: LLMConfig
    agents: dict[str, AgentConfig]
    channels: dict[str, ChannelConfig]
    heartbeats: dict[str, HeartbeatConfig]
    permissions: PermissionsConfig

    @property
    def sessions_dir(self) -> Path:
        return self.workspace / "sessions"

    @property
    def memory_dir(self) -> Path:
        return self.workspace / "memory"

    @property
    def approvals_file(self) -> Path:
        return self.workspace / "exec-approvals.json"

    def ensure_dirs(self) -> None:
        """Create workspace directories if they don't exist."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML configuration file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    raw = _resolve_env_vars(raw)

    workspace = Path(raw.get("workspace", "~/.quickdraw")).expanduser()

    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        provider=llm_raw.get("provider", "anthropic"),
        model=llm_raw.get("model", "claude-sonnet-4-5-20250929"),
        max_tokens=llm_raw.get("max_tokens", 4096),
    )

    agents: dict[str, AgentConfig] = {}
    for agent_id, agent_raw in raw.get("agents", {}).items():
        soul_path = agent_raw.get("soul", "SOUL.md")
        if not Path(soul_path).is_absolute():
            soul_path = str(workspace / soul_path)
        agents[agent_id] = AgentConfig(
            name=agent_raw.get("name", agent_id.title()),
            soul_path=soul_path,
            model=agent_raw.get("model"),
        )

    if not agents:
        agents["main"] = AgentConfig(
            name="Jarvis",
            soul_path=str(workspace / "SOUL.md"),
        )

    channels: dict[str, ChannelConfig] = {}
    for ch_id, ch_raw in raw.get("channels", {}).items():
        if isinstance(ch_raw, dict):
            enabled = ch_raw.pop("enabled", True)
            channels[ch_id] = ChannelConfig(
                kind=ch_id, enabled=enabled, settings=ch_raw,
            )
        else:
            channels[ch_id] = ChannelConfig(kind=ch_id, enabled=bool(ch_raw))

    heartbeats: dict[str, HeartbeatConfig] = {}
    for hb_id, hb_raw in raw.get("heartbeats", {}).items():
        heartbeats[hb_id] = HeartbeatConfig(
            name=hb_id,
            schedule=hb_raw["schedule"],
            agent=hb_raw.get("agent", "main"),
            prompt=hb_raw["prompt"],
        )

    perm_raw = raw.get("permissions", {})
    default_safe = PermissionsConfig().safe_commands
    permissions = PermissionsConfig(
        mode=perm_raw.get("mode", "ask"),
        safe_commands=perm_raw.get("safe_commands", default_safe),
    )

    return Config(
        workspace=workspace,
        llm=llm,
        agents=agents,
        channels=channels,
        heartbeats=heartbeats,
        permissions=permissions,
    )
