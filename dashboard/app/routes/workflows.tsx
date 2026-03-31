import { useState } from "react";
import { WorkflowStream } from "~/components/WorkflowStream";
import {
  Search,
  GitBranch,
  ExternalLink,
} from "lucide-react";

const TEMPORAL_UI =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8233`
    : "http://localhost:8233";

export default function WorkflowsPage() {
  const [workflowId, setWorkflowId] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);

  const apiBase =
    typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.hostname}:8080/v1`
      : "http://localhost:8080/v1";

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
            Workflows
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Stream live results or inspect full history in Temporal
          </p>
        </div>
        <a
          href={TEMPORAL_UI}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          <img
            src="https://avatars.githubusercontent.com/u/56493103?s=20"
            alt=""
            className="w-4 h-4 rounded"
          />
          Temporal UI
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      {/* Quick stream */}
      <div className="card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-200">
          Stream a Workflow
        </h2>
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && workflowId.trim())
                  setActiveId(workflowId.trim());
              }}
              placeholder="Paste a workflow ID..."
              className="input w-full pl-10 font-mono text-sm"
            />
          </div>
          <button
            onClick={() => {
              if (workflowId.trim()) setActiveId(workflowId.trim());
            }}
            disabled={!workflowId.trim()}
            className="btn-primary flex items-center gap-2"
          >
            <GitBranch className="w-4 h-4" />
            Stream
          </button>
        </div>
        <p className="text-xs text-zinc-600">
          Streams SSE events from the Go control plane. For full execution
          history, event replay, and query/signal interfaces, use{" "}
          <a
            href={TEMPORAL_UI}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sand-400 hover:underline"
          >
            Temporal UI
          </a>
          .
        </p>
      </div>

      {/* Active stream or empty state */}
      {activeId ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-200">
              Live Stream
            </h2>
            <a
              href={`${TEMPORAL_UI}/namespaces/default/workflows/${activeId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-sand-400 hover:text-sand-300 flex items-center gap-1"
            >
              View in Temporal <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <WorkflowStream
            workflowId={activeId}
            sseUrl={`${apiBase}/events/stream?workflow_id=${activeId}`}
          />
        </div>
      ) : (
        <div className="card p-12 text-center">
          <GitBranch className="w-8 h-8 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">
            Enter a workflow ID above to stream live results
          </p>
          <p className="text-xs text-zinc-600 mt-2">
            Or start a new run from the{" "}
            <a href="/run" className="text-sand-400 hover:underline">
              Run page
            </a>{" "}
            — it auto-streams
          </p>
        </div>
      )}
    </div>
  );
}
