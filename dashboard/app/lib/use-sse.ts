import { useEffect, useRef, useState, useCallback } from "react";

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

interface UseSSEOptions {
  url: string | null;
  onEvent?: (event: SSEEvent) => void;
}

export function useSSE({ url, onEvent }: UseSSEOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!url) return;

    const es = new EventSource(url);
    sourceRef.current = es;

    const handleEvent = (type: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const event: SSEEvent = { type, data, timestamp: Date.now() };
        setEvents((prev) => [...prev, event]);
        onEvent?.(event);

        if (type === "result" || type === "error") {
          setDone(true);
          es.close();
          setConnected(false);
        }
        if (type === "status" && ["failed", "cancelled", "terminated", "timed_out"].includes(data.status)) {
          setDone(true);
          es.close();
          setConnected(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.addEventListener("connected", (e: MessageEvent) => {
      setConnected(true);
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "connected", data, timestamp: Date.now() }]);
      } catch {
        // ignore
      }
    });
    es.addEventListener("progress", handleEvent("progress"));
    es.addEventListener("result", handleEvent("result"));
    es.addEventListener("status", handleEvent("status"));
    es.addEventListener("error", handleEvent("error"));

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

  const latestResult = events
    .filter((e) => e.type === "result" || e.type === "progress")
    .at(-1);

  return { events, connected, done, close, latestResult };
}
