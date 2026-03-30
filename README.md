# QuickDraw

An agentic framework for building "always-on" AI agents with persistent memory, multi-channel presence, and tool use.

## What It Does

QuickDraw gives you a personal AI assistant that:

- **Lives in your messaging apps** — Discord, terminal REPL, HTTP API (more channels coming)
- **Remembers everything** — persistent sessions (JSONL) and long-term memory across session resets
- **Uses tools** — shell commands, file I/O, web search, memory storage
- **Runs on a schedule** — heartbeat tasks fire on cron without you asking
- **Supports multiple agents** — route messages to specialized agents (e.g. `/research`)
- **Runs on your hardware** — laptop, VPS, Mac Mini — always on, under your control

## Quick Start

```bash
# Install
pip install -e .

# For Discord support
pip install -e '.[discord]'

# For multi-provider LLM support (OpenAI + Gemini adapters)
pip install -e '.[llm]'

# Initialize workspace
quickdraw init

# Set API keys (use whichever providers you configure)
export ANTHROPIC_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...

# Run
quickdraw run
```

This starts the REPL channel by default. Edit `~/.quickdraw/config.yaml` to enable Discord, HTTP API, or heartbeats.

## Architecture

```
Channel (Discord / REPL / HTTP)
  → Gateway (routes to agent, manages sessions)
    → Command Queue (per-session lock)
      → Agent Loop (LLM + tool execution cycle)
        → Session Manager (JSONL persistence)
        → Tool Registry (execute tools)
        → Memory System (long-term storage)
        → Context Compaction (summarize when context is full)
```

## Configuration

Copy `config.example.yaml` to `~/.quickdraw/config.yaml`:

```yaml
workspace: ~/.quickdraw

llm:
  # Ordered provider failover (tries top -> bottom)
  max_tokens: 4096
  providers:
    - provider: anthropic
      model: claude-sonnet-4-5-20250929
    - provider: openai
      model: gpt-4o-mini
      api_key: ${OPENAI_API_KEY}
    - provider: gemini
      model: gemini-2.0-flash
      api_key: ${GEMINI_API_KEY}

agents:
  main:
    name: Jarvis
    soul: SOUL.md

channels:
  repl:
    enabled: true
  discord:
    enabled: true
    token: ${DISCORD_BOT_TOKEN}
    session_scope: per-user

heartbeats:
  morning-briefing:
    schedule: "30 7 * * *"
    agent: main
    prompt: "Good morning! Give me a motivational quote."

permissions:
  mode: ask
  safe_commands: [ls, cat, date, pwd, git, python]
```

You can also keep legacy single-provider config:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  max_tokens: 4096
```

### Provider Notes

- Anthropic currently supports full tool-use in the agent loop.
- OpenAI and Gemini currently run as text-only fallback providers (no tool calls yet).
- If Anthropic is rate-limited/down, QuickDraw can still reply through fallback providers.

## Key Concepts

**SOUL.md** — A markdown file defining the agent's personality, injected as the system prompt on every LLM call. Edit `~/.quickdraw/SOUL.md` to customize.

**Sessions** — JSONL files, one per conversation. Append-only for crash safety. Automatically compacted when they approach the context window limit.

**Memory** — File-based persistent storage (`save_memory` / `memory_search` tools). Survives session resets. Shared across agents.

**Heartbeats** — Cron-scheduled agent tasks with isolated sessions, so they don't clutter your conversations.

**Gateway** — One central process managing all channels. Same agent, same sessions, same memory — regardless of which app you message from.

## Project Structure

```
quickdraw/
├── __main__.py          # CLI: quickdraw run / quickdraw init
├── config.py            # YAML config loader with ${ENV_VAR} support
├── gateway.py           # Central orchestrator
├── router.py            # Multi-agent message routing
├── heartbeat.py         # Cron-based scheduled tasks
├── llm/
│   ├── base.py          # Common LLM interface
│   ├── router.py        # Provider failover router
│   ├── anthropic_client.py
│   ├── openai_client.py
│   └── gemini_client.py
├── core/
│   ├── session.py       # JSONL session persistence
│   ├── loop.py          # Agent loop (LLM + tool cycle)
│   ├── queue.py         # Per-session async locking
│   ├── compaction.py    # Context window summarization
│   ├── memory.py        # Long-term memory store
│   └── permissions.py   # Command safety + approvals
├── tools/
│   ├── registry.py      # Tool registration system
│   ├── shell.py         # Shell command execution
│   ├── filesystem.py    # File read/write
│   ├── memory_tools.py  # save_memory, memory_search
│   └── web.py           # Web search (placeholder)
└── channels/
    ├── base.py          # Abstract channel interface
    ├── discord_channel.py
    ├── repl.py
    ├── http_api.py
    └── signal_channel.py
```

## License

MIT
