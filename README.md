# QuickDraw

An agentic workflow platform for building durable, multi-agent AI systems with persistent memory, multi-channel presence, and enterprise-grade orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Dashboard (Remix)  :3000                               │
│  ─ pack browser, run submission, SSE streaming          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Go Control Plane  :8080                                │
│  ─ API edge, auth, tenant routing, SSE, reverse proxy   │
└──────────┬───────────────────────────┬──────────────────┘
           │                           │
┌──────────▼──────────┐   ┌────────────▼─────────────────┐
│  Temporal  :7233     │   │  Python Agent Runtime  :5050 │
│  ─ durable workflows │   │  ─ channels (HTTP/Discord/   │
│  ─ retries, recovery │   │    Teams/REPL)               │
│  ─ approval gates    │   │  ─ gateway → Temporal bridge │
└──────────┬──────────┘   └──────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────┐
│  Python Temporal Worker                                 │
│  ─ execute_agent_turn (tool-isolated, SOUL-aware)       │
│  ─ route_message (LLM-powered pack classification)      │
│  ─ resolve_workflow (multi-step chain execution)         │
│  ─ PackMultiStepWorkflow (agent chaining + approvals)   │
│  ─ RouterWorkflow (top-level dispatcher)                │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export SERPER_API_KEY=...          # optional, enables real web search

# Start the full stack
docker compose up --build

# Or run locally (Python only, no Temporal)
pip install -e '.[teams]'
quickdraw run
```

### Ports

| Service | Port | URL |
|---------|------|-----|
| Dashboard | 3000 | http://localhost:3000 |
| Go Control Plane | 8080 | http://localhost:8080 |
| Python HTTP Channel | 5050 | http://localhost:5050 |
| Temporal UI | 8233 | http://localhost:8233 |

## Packs

Packs are drop-in vertical agent configurations. Each pack is a directory with a `MANIFEST.yaml` defining agents, tools, and multi-step workflows.

| Pack | Agents | Workflows | Custom Tools |
|------|--------|-----------|--------------|
| **GovCon** | Proposal Analyst, Proposal Writer, Compliance Checker, Capture Strategist, DCAA Auditor | Proposal Optimization, Compliance Review, Capture Analysis, Invoice Audit | `neuroscore` |
| **Sales** | Sales Rep, Sales Analyst | Lead Qualification, Deal Review | — |
| **Billing** | Invoice Processor, Collections Agent, Finance Analyst | Invoice Processing, Collections | — |
| **Executive Assistant** | EA, Research Specialist | Meeting Prep, Research Brief | — |

### Creating a Pack

```yaml
# packs/my-vertical/MANIFEST.yaml
id: my-vertical
name: My Vertical
description: What this pack does

agents:
  my-agent:
    name: My Agent
    soul: souls/my-agent.md    # system prompt
    tools: [web_search, filesystem, memory]

workflows:
  my-workflow:
    name: My Workflow
    trigger: "when to route here"
    steps:
      - agent: my-agent
        prompt_template: |
          Do something with: {input}

router:
  description: "Keywords that trigger routing to this pack"
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

**SOUL.md** — Markdown system prompt defining an agent's personality, domain expertise, and working principles.

**Pack System** — Vertical specialization via `MANIFEST.yaml`. Each pack declares agents (with SOULs and tool permissions), multi-step workflows (with approval gates), and custom tools.

**Router Workflow** — LLM-powered classifier that reads all loaded packs and dispatches incoming messages to the best-fit agent or workflow.

**Durable Execution** — All workflows run through Temporal with retry policies, heartbeats, and crash recovery. Kill the worker mid-task — it resumes.

**Custom Tools** — Packs can ship Python tool modules in `tools/`. The loader dynamically imports them and registers in the agent's tool registry.

**Channels** — HTTP, Discord, REPL, MS Teams. All channel messages bridge to Temporal when connected.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `SERPER_API_KEY` | No | Enables real web search (serper.dev) |
| `MS_APP_ID` | No | Teams bot app ID |
| `MS_APP_PASSWORD` | No | Teams bot secret |
| `MS_TENANT_ID` | No | Azure AD tenant |

## Project Structure

```
├── quickdraw/                 # Python agent runtime
│   ├── core/                  # session, loop, memory, permissions, compaction
│   ├── tools/                 # shell, filesystem, memory, web search
│   ├── channels/              # HTTP, Discord, REPL, Teams
│   ├── workflows/             # Temporal: activities, worker, durable_run,
│   │                          #   router_workflow, pack_workflow
│   └── packs/                 # Pack loader + router context builder
├── controlplane/              # Go API edge (chi router, Temporal client, SSE)
├── dashboard/                 # Remix + Tailwind dashboard
├── packs/                     # Vertical pack definitions
│   ├── govcon/                #   GovCon (neuroscore tool, 5 agents, 4 workflows)
│   ├── sales/                 #   Sales (2 agents, 2 workflows)
│   ├── billing/               #   Billing (3 agents, 2 workflows)
│   └── executive-assistant/   #   EA (2 agents, 2 workflows)
└── docker-compose.yml         # Full stack orchestration
```

## License

MIT
