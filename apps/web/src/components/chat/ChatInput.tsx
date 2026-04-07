import { useState, useRef, useCallback } from "react";
import {
  FlexBox,
  Button,
} from "@ui5/webcomponents-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
}

export function ChatInput({ onSend, onStop, disabled, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setValue("");
  }, [value, disabled, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="chat-composer-shell">
      <div className="chat-composer">
        <div className="chat-composer__header">
          <div>
            <div className="chat-composer__label">Compose</div>
            <div className="chat-composer__hint">
              {disabled
                ? "Select a SAP system to activate the workspace composer."
                : "Enter to send • Shift+Enter for newline"}
            </div>
          </div>
        </div>
      <FlexBox alignItems="End" style={{ gap: 10 }}>
        <div className="chat-composer__field-wrap">
          <textarea
            ref={textAreaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? "Select a SAP system to start chatting..."
                : "Ask about SAP objects, run commands, or explore code..."
            }
            disabled={disabled}
            rows={2}
            className="chat-composer__textarea"
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--sapField_Active_BorderColor)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--sapField_BorderColor)";
            }}
          />
          <div className="chat-composer__status">
            {isStreaming ? "Generating..." : `${value.trim().length} characters ready`}
          </div>
        </div>
        <FlexBox direction="Column" style={{ gap: 6 }}>
          {isStreaming ? (
            <Button
              icon="stop"
              design="Negative"
              tooltip="Stop generation"
              onClick={() => onStop?.()}
            />
          ) : (
            <Button
              icon="paper-plane"
              design="Emphasized"
              tooltip="Send message"
              disabled={!value.trim() || disabled}
              onClick={handleSend}
            />
          )}
        </FlexBox>
      </FlexBox>
      </div>
    </div>
  );
}
