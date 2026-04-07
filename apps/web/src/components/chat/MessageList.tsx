import { Avatar } from "@ui5/webcomponents-react";
import type { ChatMessage } from "@sap-copilot/shared";
import { ToolCallCard } from "./ToolCallCard";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <>
      {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
    </>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isStreaming = message.role === "assistant" && !message.content && (!message.toolCalls || message.toolCalls.length === 0);

  return (
    <div className={`chat-message ${isUser ? "chat-message--user" : "chat-message--assistant"}`}>
      {/* Role label row */}
      <div className="chat-message__meta">
        <Avatar size="XS" colorScheme={isUser ? "Accent6" : "Accent1"} icon={isUser ? "customer" : "ai"} />
        <span className="chat-message__author">
          {isUser ? "You" : "SAP Copilot"}
        </span>
      </div>

      {/* Bubble */}
      <div className={`chat-message__bubble ${isUser ? "chat-message__bubble--user" : "chat-message__bubble--assistant"}`}>
        {isStreaming ? <span className="typing-cursor chat-message__thinking">Thinking&hellip;</span> : message.content}
      </div>

      {/* Tool calls */}
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="chat-message__tools">
          {message.toolCalls.map((tc) => <ToolCallCard key={tc.id} toolCall={tc} />)}
        </div>
      )}

      {/* Timestamp */}
      <div className="chat-message__timestamp">
        {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </div>
    </div>
  );
}
