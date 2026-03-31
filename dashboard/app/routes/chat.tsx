import { ChatInterface } from "~/components/ChatInterface";
import { useChat } from "~/hooks/useChat";
import { useSessions } from "~/hooks/useSessions";

export default function ChatPage() {
  const {
    messages,
    sendMessage,
    isThinking,
    sessionKey,
    delegationEvents,
    clearChat,
    loadSession,
  } = useChat();

  const {
    sessions,
    loading: sessionsLoading,
    refresh: refreshSessions,
  } = useSessions();

  return (
    <ChatInterface
      messages={messages}
      onSend={sendMessage}
      isThinking={isThinking}
      sessionKey={sessionKey}
      delegationEvents={delegationEvents}
      onClear={() => {
        clearChat();
        setTimeout(refreshSessions, 500);
      }}
      onLoadSession={loadSession}
      sessions={sessions}
      sessionsLoading={sessionsLoading}
      onRefreshSessions={refreshSessions}
    />
  );
}
