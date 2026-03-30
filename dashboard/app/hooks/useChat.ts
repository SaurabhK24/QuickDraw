import { useState, useRef, useCallback, useEffect } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  metadata?: {
    workflow_id?: string;
    step_count?: number;
    routed_to?: string;
    status?: string;
  };
}

export interface DelegationEvent {
  type: string;
  agent_id?: string;
  agent_name?: string;
  task_preview?: string;
  response_preview?: string;
  parallel?: boolean;
  count?: number;
  agent_ids?: string[];
  agent_names?: string[];
  error?: string;
  depth?: number;
  ts?: number;
}

interface UseChatReturn {
  messages: ChatMessage[];
  sendMessage: (text: string) => void;
  isThinking: boolean;
  sessionKey: string;
  currentWorkflowId: string | null;
  delegationEvents: DelegationEvent[];
  clearChat: () => void;
  loadSession: (key: string) => void;
}

const STORAGE_KEY = "quickdraw_chat_session";

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function getStoredSessionKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

function getOrCreateSessionKey(): string {
  const stored = getStoredSessionKey();
  if (stored) return stored;
  const key = `chat:${generateId()}`;
  if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, key);
  return key;
}

function getApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:8080";
  return `${window.location.protocol}//${window.location.hostname}:8080`;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(
    null
  );
  const [delegationEvents, setDelegationEvents] = useState<DelegationEvent[]>(
    []
  );
  const sessionKeyRef = useRef(getOrCreateSessionKey());
  const eventSourceRef = useRef<EventSource | null>(null);
  const loadedRef = useRef(false);

  const loadMessagesFromServer = useCallback((key: string) => {
    const apiBase = getApiBase();
    fetch(`${apiBase}/sessions/${encodeURIComponent(key)}`)
      .then((res) => (res.ok ? res.json() : { messages: [] }))
      .then((data) => {
        if (data.messages && data.messages.length > 0) {
          const restored: ChatMessage[] = data.messages.map(
            (m: { role: string; content: string }, i: number) => ({
              id: `restored-${i}`,
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: Date.now() - (data.messages.length - i) * 1000,
            })
          );
          setMessages(restored);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    loadMessagesFromServer(sessionKeyRef.current);
  }, [loadMessagesFromServer]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isThinking) return;

      eventSourceRef.current?.close();
      setDelegationEvents([]);

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsThinking(true);

      try {
        // Call the Go API directly — avoids Remix action issues in Docker
        const apiBase = getApiBase();
        const res = await fetch(`${apiBase}/v1/chat/send`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": "default",
          },
          body: JSON.stringify({
            user_text: text,
            session_key: sessionKeyRef.current,
          }),
        });

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || `Server error ${res.status}`);
        }

        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          throw new Error(
            "API returned non-JSON response. Is the control plane running?"
          );
        }

        const data = await res.json();
        const workflowId = data.workflow_id;
        const sessionKey = data.session_key || sessionKeyRef.current;
        setCurrentWorkflowId(workflowId);

        const sseParams = new URLSearchParams({
          workflow_id: workflowId,
          session_key: sessionKey,
        });
        const es = new EventSource(
          `${apiBase}/v1/events/stream?${sseParams}`
        );
        eventSourceRef.current = es;

        es.addEventListener("delegation", (e: MessageEvent) => {
          try {
            const d = JSON.parse(e.data);
            setDelegationEvents((prev) => [...prev, d]);
          } catch {
            /* ignore */
          }
        });

        es.addEventListener("result", (e: MessageEvent) => {
          try {
            const d = JSON.parse(e.data);
            const assistantMsg: ChatMessage = {
              id: generateId(),
              role: "assistant",
              content: d.response_text || "[No response]",
              timestamp: Date.now(),
              metadata: {
                workflow_id: workflowId,
                step_count: d.step_count,
                routed_to: d.routed_to,
                status: "completed",
              },
            };
            setMessages((prev) => [...prev, assistantMsg]);
          } catch {
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: "assistant",
                content: "[Failed to parse response]",
                timestamp: Date.now(),
                metadata: { status: "error" },
              },
            ]);
          }
          setIsThinking(false);
          setCurrentWorkflowId(null);
          setDelegationEvents([]);
          es.close();
          eventSourceRef.current = null;
        });

        es.addEventListener("error", () => {
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              role: "system",
              content: "Connection lost. The workflow may still be running.",
              timestamp: Date.now(),
              metadata: { status: "error" },
            },
          ]);
          setIsThinking(false);
          setCurrentWorkflowId(null);
          setDelegationEvents([]);
          es.close();
          eventSourceRef.current = null;
        });

        es.addEventListener("status", (e: MessageEvent) => {
          try {
            const d = JSON.parse(e.data);
            if (
              ["failed", "cancelled", "terminated", "timed_out"].includes(
                d.status
              )
            ) {
              setMessages((prev) => [
                ...prev,
                {
                  id: generateId(),
                  role: "system",
                  content: `Workflow ${d.status}.`,
                  timestamp: Date.now(),
                  metadata: { status: d.status },
                },
              ]);
              setIsThinking(false);
              setCurrentWorkflowId(null);
              setDelegationEvents([]);
              es.close();
              eventSourceRef.current = null;
            }
          } catch {
            /* ignore */
          }
        });
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "system",
            content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
            timestamp: Date.now(),
            metadata: { status: "error" },
          },
        ]);
        setIsThinking(false);
        setCurrentWorkflowId(null);
      }
    },
    [isThinking]
  );

  const clearChat = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setMessages([]);
    setIsThinking(false);
    setCurrentWorkflowId(null);
    setDelegationEvents([]);
    const newKey = `chat:${generateId()}`;
    sessionKeyRef.current = newKey;
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, newKey);
    }
    loadedRef.current = true;
  }, []);

  const loadSession = useCallback(
    (key: string) => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      setMessages([]);
      setIsThinking(false);
      setCurrentWorkflowId(null);
      setDelegationEvents([]);
      sessionKeyRef.current = key;
      if (typeof window !== "undefined") {
        localStorage.setItem(STORAGE_KEY, key);
      }
      loadMessagesFromServer(key);
    },
    [loadMessagesFromServer]
  );

  return {
    messages,
    sendMessage,
    isThinking,
    sessionKey: sessionKeyRef.current,
    currentWorkflowId,
    delegationEvents,
    clearChat,
    loadSession,
  };
}
