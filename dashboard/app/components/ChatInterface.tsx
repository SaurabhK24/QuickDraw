import { useState, useRef, useEffect } from "react";
import { Markdown } from "~/components/Markdown";
import {
  Send,
  Loader2,
  Zap,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  MessageSquare,
  Clock,
  Terminal,
  Wrench,
  GitBranch,
  CheckCircle2,
  AlertCircle,
  Layers,
  ArrowRight,
  Plus,
} from "lucide-react";
import type { ChatMessage, DelegationEvent } from "~/hooks/useChat";
import type { SessionSummary } from "~/hooks/useSessions";

// ── Types ──────────────────────────────────────────────────

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  isThinking: boolean;
  sessionKey: string;
  delegationEvents: DelegationEvent[];
  onClear: () => void;
  onLoadSession: (key: string) => void;
  sessions: SessionSummary[];
  sessionsLoading: boolean;
  onRefreshSessions: () => void;
}

// ── Helpers ────────────────────────────────────────────────

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function truncate(s: string, max: number) {
  return s.length > max ? s.slice(0, max) + "…" : s;
}

// ── Session Sidebar ────────────────────────────────────────

function SessionSidebar({
  sessions,
  loading,
  currentKey,
  onSelect,
  onNew,
  onRefresh,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  currentKey: string;
  onSelect: (key: string) => void;
  onNew: () => void;
  onRefresh: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-3 pt-3 pb-2">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-zinc-700/60 text-xs font-medium text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 hover:border-zinc-600 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          New Session
        </button>
      </div>

      <div className="px-3 pb-1.5 flex items-center justify-between">
        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">
          History
        </span>
        <button
          onClick={onRefresh}
          className="p-1 rounded text-zinc-600 hover:text-zinc-400 transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-px">
        {loading && sessions.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-4 h-4 text-zinc-700 animate-spin" />
          </div>
        )}

        {!loading && sessions.length === 0 && (
          <div className="text-center py-8">
            <Terminal className="w-5 h-5 text-zinc-800 mx-auto mb-2" />
            <p className="text-[10px] text-zinc-700">No sessions yet</p>
          </div>
        )}

        {sessions.map((s) => {
          const isCurrent = s.key === currentKey;
          return (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={`w-full text-left px-2.5 py-2 rounded-md text-xs transition-all ${
                isCurrent
                  ? "bg-zinc-800 text-zinc-200 border-l-2 border-sand-500"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
              }`}
            >
              <p className="truncate leading-snug font-medium">
                {s.first_user_message || "Empty session"}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                {s.workflow && (
                  <span className="text-[9px] font-mono text-sand-600">
                    {s.workflow}
                  </span>
                )}
                {s.step_count > 0 && (
                  <span className="text-[9px] text-zinc-700">
                    {s.step_count} steps
                  </span>
                )}
                <span className="text-[9px] text-zinc-700">
                  {s.total_messages} msgs
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Tool Call Block ─────────────────────────────────────────

function ToolCallBlock({ name, input }: { name: string; input: any }) {
  const [expanded, setExpanded] = useState(false);
  const inputStr =
    typeof input === "string" ? input : JSON.stringify(input, null, 2);
  const preview = typeof input === "object"
    ? Object.entries(input)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ")
    : inputStr;

  return (
    <div className="my-1 font-mono text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-sand-500/80 hover:text-sand-400 transition-colors group"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 flex-shrink-0" />
        )}
        <Wrench className="w-3 h-3 flex-shrink-0 text-sand-600" />
        <span className="text-sand-400 font-semibold">{name}</span>
        {!expanded && (
          <span className="text-zinc-600 truncate max-w-md">
            ({truncate(preview, 80)})
          </span>
        )}
      </button>
      {expanded && (
        <pre className="mt-1 ml-5 p-2 bg-zinc-950 border border-zinc-800/60 rounded text-[11px] text-zinc-400 overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
          {inputStr}
        </pre>
      )}
    </div>
  );
}

// ── Delegation Progress ─────────────────────────────────────

function DelegationProgress({ events }: { events: DelegationEvent[] }) {
  if (events.length === 0) return null;

  const completed = new Set<string>();
  const errored = new Set<string>();
  for (const e of events) {
    if (e.type === "delegation_end") completed.add(e.agent_id || "");
    if (e.type === "delegation_error") errored.add(e.agent_id || "");
  }

  const isParallel = events.some((e) => e.type === "parallel_start");

  return (
    <div className="space-y-1 font-mono text-xs">
      {isParallel && (
        <div className="flex items-center gap-1.5 text-violet-400/80">
          <Layers className="w-3 h-3" />
          <span>parallel fan-out</span>
        </div>
      )}
      {events
        .filter((e) => e.type === "delegation_start")
        .map((evt, i) => {
          const done = completed.has(evt.agent_id || "");
          const err = errored.has(evt.agent_id || "");
          return (
            <div key={i} className="flex items-center gap-1.5">
              {done ? (
                <CheckCircle2 className="w-3 h-3 text-emerald-500 flex-shrink-0" />
              ) : err ? (
                <AlertCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
              ) : (
                <Loader2 className="w-3 h-3 text-sand-500 animate-spin flex-shrink-0" />
              )}
              <ArrowRight className="w-2.5 h-2.5 text-zinc-700" />
              <span className={done ? "text-zinc-500" : "text-zinc-300"}>
                {evt.agent_name || evt.agent_id}
              </span>
              <span className="text-zinc-700 truncate">
                {done ? "done" : truncate(evt.task_preview || "", 50)}
              </span>
            </div>
          );
        })}
      {events[events.length - 1]?.type === "delegation_end" &&
        completed.size > 0 && (
          <div className="flex items-center gap-1.5 text-zinc-600">
            <GitBranch className="w-3 h-3" />
            <span>synthesizing {completed.size} outputs…</span>
          </div>
        )}
    </div>
  );
}

// ── Message Entry (Claude Code style) ───────────────────────

function EntryBlock({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    return (
      <div className="py-1.5 px-3 text-xs text-zinc-600 font-mono border-l-2 border-zinc-800">
        {message.content}
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="py-3 group">
        <div className="flex items-start gap-2">
          <span className="text-sand-500 font-mono text-xs font-bold flex-shrink-0 mt-0.5 select-none">
            &gt;
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-zinc-100 whitespace-pre-wrap leading-relaxed">
              {message.content}
            </p>
          </div>
          <span className="text-[10px] text-zinc-700 font-mono flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    );
  }

  // Assistant
  return (
    <div className="py-3 border-l-2 border-zinc-800/50 pl-3 ml-1">
      <div className="flex items-center gap-2 mb-2">
        <Zap className="w-3 h-3 text-sand-500" />
        <span className="text-[10px] text-zinc-600 font-mono">
          {message.metadata?.routed_to || "quickdraw"}
          {message.metadata?.step_count
            ? ` · ${message.metadata.step_count} steps`
            : ""}
        </span>
      </div>
      <div className="prose-sm">
        <Markdown>{message.content}</Markdown>
      </div>
    </div>
  );
}

// ── Thinking State ──────────────────────────────────────────

function ThinkingBlock({ events }: { events: DelegationEvent[] }) {
  return (
    <div className="py-3 border-l-2 border-sand-500/30 pl-3 ml-1">
      <div className="flex items-center gap-2 mb-2">
        <Loader2 className="w-3 h-3 text-sand-500 animate-spin" />
        <span className="text-[10px] text-zinc-500 font-mono">
          {events.length > 0 ? "orchestrating" : "thinking"}
        </span>
      </div>
      {events.length > 0 ? (
        <DelegationProgress events={events} />
      ) : (
        <div className="flex items-center gap-2 font-mono text-xs text-zinc-600">
          <span className="inline-block w-1.5 h-4 bg-sand-500/60 animate-pulse" />
        </div>
      )}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────

export function ChatInterface({
  messages,
  onSend,
  isThinking,
  sessionKey,
  delegationEvents,
  onClear,
  onLoadSession,
  sessions,
  sessionsLoading,
  onRefreshSessions,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking, delegationEvents]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isThinking) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] -mx-8 -my-8">
      {/* ── Sidebar ── */}
      <div className="w-56 border-r border-zinc-800/60 bg-zinc-950/80 flex-shrink-0">
        <SessionSidebar
          sessions={sessions}
          loading={sessionsLoading}
          currentKey={sessionKey}
          onSelect={onLoadSession}
          onNew={onClear}
          onRefresh={onRefreshSessions}
        />
      </div>

      {/* ── Main Area ── */}
      <div className="flex-1 flex flex-col min-w-0 bg-zinc-950/40">
        {/* Header bar */}
        <div className="flex items-center gap-3 px-5 py-2.5 border-b border-zinc-800/60">
          <Terminal className="w-4 h-4 text-zinc-600" />
          <code className="text-[11px] text-zinc-500">{sessionKey}</code>
          {isThinking && (
            <span className="ml-auto flex items-center gap-1.5 text-[10px] text-sand-500 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-sand-500 animate-pulse" />
              running
            </span>
          )}
        </div>

        {/* Execution log */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {messages.length === 0 && !isThinking && (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="text-center max-w-lg">
                <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-5 h-5 text-sand-500" />
                </div>
                <p className="text-sm text-zinc-400 mb-1 font-medium">
                  QuickDraw Swarm
                </p>
                <p className="text-xs text-zinc-600 mb-6 leading-relaxed max-w-sm mx-auto">
                  Type a task below. The router classifies it, picks the right
                  agents or workflow, and you'll see every tool call and
                  delegation in real-time.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    "Qualify Booz Allen Hamilton as a lead for AI consulting",
                    "Full go-to-market analysis for selling to SAIC",
                    "Review this contract for FAR/DFARS compliance gaps",
                    "Research competitive landscape for DOD cloud RFPs",
                  ].map((hint) => (
                    <button
                      key={hint}
                      onClick={() => onSend(hint)}
                      className="text-left text-[11px] text-zinc-500 hover:text-zinc-300 bg-zinc-900/50 hover:bg-zinc-900 border border-zinc-800/60 hover:border-zinc-700 rounded-md p-2.5 transition-all font-mono leading-snug"
                    >
                      <span className="text-sand-600 mr-1">&gt;</span>
                      {hint}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <EntryBlock key={msg.id} message={msg} />
          ))}

          {isThinking && <ThinkingBlock events={delegationEvents} />}

          <div ref={bottomRef} />
        </div>

        {/* Input — terminal style */}
        <form onSubmit={handleSubmit} className="border-t border-zinc-800/60">
          <div className="flex items-center px-5 py-3 gap-2">
            <span className="text-sand-500 font-mono text-sm font-bold select-none">
              &gt;
            </span>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={isThinking ? "Waiting for response…" : "Enter a task…"}
              disabled={isThinking}
              className="flex-1 bg-transparent text-sm text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isThinking}
              className="p-1.5 rounded text-zinc-600 hover:text-sand-400 disabled:opacity-30 transition-colors"
            >
              {isThinking ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
