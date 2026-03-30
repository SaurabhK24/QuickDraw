import { useSSE, type SSEEvent } from "~/lib/use-sse";
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  Radio,
  ChevronRight,
} from "lucide-react";

interface WorkflowStreamProps {
  workflowId: string;
  sseUrl: string;
}

function EventIcon({ type, status }: { type: string; status?: string }) {
  if (type === "result" || status === "completed") {
    return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
  }
  if (type === "error" || status === "failed") {
    return <AlertCircle className="w-4 h-4 text-red-400" />;
  }
  if (type === "connected") {
    return <Radio className="w-4 h-4 text-sand-400" />;
  }
  return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function WorkflowStream({ workflowId, sseUrl }: WorkflowStreamProps) {
  const { events, connected, done, latestResult } = useSSE({ url: sseUrl });

  const status: string = done
    ? String(latestResult?.data?.status ?? "completed")
    : connected
    ? "streaming"
    : "connecting";

  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              done
                ? status === "completed"
                  ? "bg-emerald-500"
                  : "bg-red-500"
                : "bg-blue-500 animate-pulse-slow"
            }`}
          />
          <span className="text-sm font-medium text-zinc-200 capitalize">
            {status}
          </span>
        </div>
        <span className="text-xs text-zinc-500 font-mono">{workflowId}</span>
      </div>

      {/* Result card */}
      {latestResult?.data?.response_text != null && (
        <div className="card p-5 animate-slide-up">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Response
          </h4>
          <div className="prose prose-invert prose-sm max-w-none text-zinc-300 whitespace-pre-wrap">
            {String(latestResult.data.response_text ?? "")}
          </div>
          {latestResult.data.step_count != null && (
            <p className="text-xs text-zinc-500 mt-3 pt-3 border-t border-zinc-800">
              {String(latestResult.data.step_count)} steps completed
            </p>
          )}
        </div>
      )}

      {/* Event timeline */}
      <div className="card divide-y divide-zinc-800/50">
        <div className="px-4 py-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Event Stream
          </h4>
        </div>
        {events.length === 0 && (
          <div className="px-4 py-8 text-center text-zinc-500 text-sm">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-zinc-600" />
            Waiting for events...
          </div>
        )}
        {events.map((event, i) => (
          <EventRow key={i} event={event} />
        ))}
      </div>
    </div>
  );
}

function EventRow({ event }: { event: SSEEvent }) {
  return (
    <div className="px-4 py-3 flex items-start gap-3 animate-slide-up">
      <div className="mt-0.5">
        <EventIcon type={event.type} status={event.data?.status as string} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold uppercase tracking-wide ${
              event.type === "result"
                ? "text-emerald-400"
                : event.type === "error"
                ? "text-red-400"
                : event.type === "connected"
                ? "text-sand-400"
                : "text-blue-400"
            }`}
          >
            {event.type}
          </span>
          <span className="text-[10px] text-zinc-600 font-mono">
            {formatTime(event.timestamp)}
          </span>
        </div>
        {event.data?.status != null && (
          <p className="text-xs text-zinc-400 mt-0.5 flex items-center gap-1">
            <ChevronRight className="w-3 h-3" />
            {String(event.data.status)}
            {event.data.step_count != null &&
              ` \u00b7 ${String(event.data.step_count)} steps`}
          </p>
        )}
      </div>
    </div>
  );
}
