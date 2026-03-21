"""CLI entry point for QuickDraw.

Usage:
    quickdraw run [--config config.yaml]   Start the gateway
    quickdraw init [--dir ~/.quickdraw]    Scaffold a new workspace
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("quickdraw")

DEFAULT_SOUL = """\
# Who You Are

**Name:** Jarvis
**Role:** Personal AI assistant

## Personality
- Be genuinely helpful, not performatively helpful
- Skip the "Great question!" — just help
- Have opinions. You're allowed to disagree
- Be concise when needed, thorough when it matters

## Boundaries
- Private things stay private
- When in doubt, ask before acting externally
- You're not the user's voice — be careful about sending messages on their behalf

## Memory
You have a long-term memory system.
- Use save_memory to store important information (user preferences, key facts, project details)
- Use memory_search at the start of conversations to recall context from previous sessions
"""

DEFAULT_CONFIG = """\
workspace: ~/.quickdraw

llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  max_tokens: 4096

agents:
  main:
    name: Jarvis
    soul: SOUL.md

channels:
  repl:
    enabled: true

permissions:
  mode: ask
  safe_commands:
    - ls
    - cat
    - head
    - tail
    - wc
    - date
    - whoami
    - echo
    - pwd
    - which
    - git
    - python
    - node
    - npm
"""


def cmd_init(args: argparse.Namespace) -> None:
    """Scaffold a new QuickDraw workspace."""
    workspace = Path(args.dir).expanduser()
    workspace.mkdir(parents=True, exist_ok=True)

    soul_path = workspace / "SOUL.md"
    if not soul_path.exists():
        soul_path.write_text(DEFAULT_SOUL)
        print(f"  Created {soul_path}")
    else:
        print(f"  Already exists: {soul_path}")

    config_path = workspace / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG)
        print(f"  Created {config_path}")
    else:
        print(f"  Already exists: {config_path}")

    for subdir in ("sessions", "memory"):
        d = workspace / subdir
        d.mkdir(exist_ok=True)

    print(f"\nWorkspace initialized at {workspace}")
    print(f"  Run: quickdraw run --config {config_path}")


def cmd_run(args: argparse.Namespace) -> None:
    """Start the QuickDraw gateway."""
    config_path = Path(args.config).expanduser()

    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        print("Run 'quickdraw init' to create a default workspace, or specify --config.")
        sys.exit(1)

    from quickdraw.config import load_config
    from quickdraw.gateway import Gateway

    config = load_config(config_path)
    gateway = Gateway(config)
    gateway.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        prog="quickdraw",
        description="QuickDraw — always-on AI agents",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Scaffold a new workspace")
    init_parser.add_argument(
        "--dir", default="~/.quickdraw",
        help="Workspace directory (default: ~/.quickdraw)",
    )

    run_parser = subparsers.add_parser("run", help="Start the gateway")
    run_parser.add_argument(
        "--config", default="~/.quickdraw/config.yaml",
        help="Path to config.yaml (default: ~/.quickdraw/config.yaml)",
    )

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
