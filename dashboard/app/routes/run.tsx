import { useState, useCallback } from "react";
import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useSearchParams } from "@remix-run/react";
import { createRun, type RunResponse } from "~/lib/api.server";
import { WorkflowStream } from "~/components/WorkflowStream";
import {
  Send,
  Route,
  Target,
  Brain,
  ChevronDown,
} from "lucide-react";

const PRESET_PROMPTS = [
  {
    label: "Proposal Optimization",
    pack: "govcon",
    prompt: "Analyze and optimize this proposal section for neural persuasion...",
  },
  {
    label: "Compliance Review",
    pack: "govcon",
    prompt: "Review this document for FAR/DFARS compliance...",
  },
  {
    label: "Capture Analysis",
    pack: "govcon",
    prompt: "Research this government contracting opportunity...",
  },
  {
    label: "Lead Qualification",
    pack: "sales",
    prompt: "Research and qualify this lead...",
  },
  {
    label: "Invoice Audit",
    pack: "billing",
    prompt: "Audit this invoice for DCAA compliance...",
  },
  {
    label: "Meeting Prep",
    pack: "executive-assistant",
    prompt: "Prepare briefing for this meeting...",
  },
];

export async function action({ request }: ActionFunctionArgs) {
  const form = await request.formData();
  const userText = form.get("user_text") as string;
  const mode = (form.get("mode") as string) || "routed";
  const agentId = form.get("agent_id") as string | undefined;

  if (!userText?.trim()) {
    return json({ error: "Message is required" }, { status: 400 });
  }

  try {
    const result = await createRun({
      user_text: userText,
      mode: mode as "routed" | "direct",
      agent_id: agentId || undefined,
    });

    return json(result);
  } catch (e) {
    return json(
      { error: e instanceof Error ? e.message : "Failed to create run" },
      { status: 500 }
    );
  }
}

export default function RunPage() {
  const fetcher = useFetcher<RunResponse & { error?: string }>();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState(searchParams.get("mode") || "routed");
  const [showPresets, setShowPresets] = useState(false);
  const [prompt, setPrompt] = useState(
    searchParams.get("prompt")?.replace(/\+/g, " ") || ""
  );

  const isSubmitting = fetcher.state !== "idle";
  const result = fetcher.data;
  const hasRun = result && "workflow_id" in result && !("error" in result);

  const apiBase =
    typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.hostname}:8080/v1`
      : "";
  const sseUrl =
    hasRun ? `${apiBase}/events/stream?workflow_id=${result.workflow_id}` : null;

  const selectPreset = useCallback(
    (p: (typeof PRESET_PROMPTS)[number]) => {
      setPrompt(p.prompt);
      setShowPresets(false);
    },
    []
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
          New Run
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Submit a task to the agentic workflow engine
        </p>
      </div>

      {/* Input form */}
      <fetcher.Form method="post" className="space-y-4">
        {/* Mode toggle */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setMode("routed")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === "routed"
                ? "bg-sand-500/15 text-sand-300 border border-sand-500/20"
                : "bg-zinc-800/50 text-zinc-400 border border-zinc-800 hover:border-zinc-700"
            }`}
          >
            <Route className="w-4 h-4" />
            Routed
          </button>
          <button
            type="button"
            onClick={() => setMode("direct")}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === "direct"
                ? "bg-sand-500/15 text-sand-300 border border-sand-500/20"
                : "bg-zinc-800/50 text-zinc-400 border border-zinc-800 hover:border-zinc-700"
            }`}
          >
            <Target className="w-4 h-4" />
            Direct
          </button>
          <input type="hidden" name="mode" value={mode} />

          <div className="ml-auto relative">
            <button
              type="button"
              onClick={() => setShowPresets(!showPresets)}
              className="btn-secondary flex items-center gap-2 text-xs"
            >
              <Brain className="w-3.5 h-3.5" />
              Presets
              <ChevronDown className="w-3 h-3" />
            </button>
            {showPresets && (
              <div className="absolute right-0 mt-2 w-72 card border border-zinc-700 shadow-xl z-10 py-1">
                {PRESET_PROMPTS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => selectPreset(p)}
                    className="w-full text-left px-4 py-2.5 hover:bg-zinc-800 transition-colors"
                  >
                    <span className="text-sm text-zinc-200">{p.label}</span>
                    <span className="text-[10px] text-zinc-500 ml-2 font-mono">
                      {p.pack}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Prompt textarea */}
        <div>
          <textarea
            name="user_text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your task... The router will automatically select the best pack and agent."
            rows={6}
            className="input w-full resize-none font-mono text-sm"
          />
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-zinc-500">
            {mode === "routed"
              ? "LLM router will classify and dispatch to the best agent/workflow"
              : "Direct execution against a single agent"}
          </p>
          <button
            type="submit"
            disabled={isSubmitting || !prompt.trim()}
            className="btn-primary flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Run
              </>
            )}
          </button>
        </div>

        {result && "error" in result && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-sm text-red-400">
            {result.error}
          </div>
        )}
      </fetcher.Form>

      {/* Streaming results */}
      {hasRun && sseUrl && (
        <div className="animate-slide-up">
          <h2 className="text-sm font-semibold text-zinc-200 mb-4">
            Workflow Execution
          </h2>
          <WorkflowStream
            workflowId={result.workflow_id}
            sseUrl={sseUrl}
          />
        </div>
      )}
    </div>
  );
}
