const API_BASE = process.env.API_URL || "http://localhost:8080/v1";
const API_ORIGIN = API_BASE.replace(/\/v1$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": "default",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

export interface RunResponse {
  workflow_id: string;
  run_id: string;
  session_key?: string;
  tenant: string;
  status: string;
  mode: string;
}

export interface ChatSession {
  key: string;
  message_count: number;
  last_message_preview: string;
  size_bytes: number;
}

export interface SessionMessage {
  role: "user" | "assistant";
  content: string;
}

export interface RunStatus {
  workflow_id: string;
  tenant: string;
  status: string;
  response_text?: string;
  step_count?: number;
  run_id?: string;
  partial?: boolean;
}

export interface Agent {
  id: string;
  name: string;
}

export async function createRun(params: {
  user_text: string;
  agent_id?: string;
  session_key?: string;
  mode?: "routed" | "direct";
}): Promise<RunResponse> {
  return apiFetch<RunResponse>("/runs", {
    method: "POST",
    body: JSON.stringify({
      user_text: params.user_text,
      agent_id: params.agent_id || "",
      session_key: params.session_key || "",
      mode: params.mode || "routed",
    }),
  });
}

export async function getRunStatus(workflowId: string): Promise<RunStatus> {
  return apiFetch<RunStatus>(`/runs/${workflowId}`);
}

export async function cancelRun(workflowId: string): Promise<void> {
  await apiFetch(`/runs/${workflowId}/cancel`, { method: "POST" });
}

export async function listAgents(): Promise<{ agents: Agent[]; tenant: string }> {
  return apiFetch("/agents");
}

export async function getHealth(): Promise<{ status: string; service: string; timestamp: string }> {
  const res = await fetch(`${API_ORIGIN}/health`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Health ${res.status}`);
  return res.json();
}

export function getSSEUrl(workflowId: string): string {
  return `${API_BASE}/events/stream?workflow_id=${workflowId}`;
}

export async function listChatSessions(): Promise<{ sessions: ChatSession[] }> {
  const res = await fetch(`${API_ORIGIN}/sessions?prefix=chat`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) return { sessions: [] };
  return res.json();
}

export async function getSessionMessages(key: string): Promise<{ messages: SessionMessage[] }> {
  const res = await fetch(`${API_ORIGIN}/sessions/${encodeURIComponent(key)}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) return { messages: [] };
  return res.json();
}
