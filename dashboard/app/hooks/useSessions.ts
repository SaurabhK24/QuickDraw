import { useState, useEffect, useCallback } from "react";

export interface SessionSummary {
  key: string;
  total_messages: number;
  first_user_message: string;
  workflow: string;
  step_count: number;
  size_bytes: number;
}

function getApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:8080";
  return `${window.location.protocol}//${window.location.hostname}:8080`;
}

export function useSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    const apiBase = getApiBase();
    fetch(`${apiBase}/sessions`)
      .then((res) => (res.ok ? res.json() : { sessions: [] }))
      .then((data) => setSessions(data.sessions || []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { sessions, loading, refresh };
}
