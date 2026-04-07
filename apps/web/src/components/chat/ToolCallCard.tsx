import { useState } from "react";
import { Icon } from "@ui5/webcomponents-react";
import type { ToolCall } from "@sap-copilot/shared";
import { TOOL_TO_CATEGORY, TOOL_CATEGORIES } from "@sap-copilot/shared";

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  const category = TOOL_TO_CATEGORY[toolCall.name] ?? "read";
  const catMeta = TOOL_CATEGORIES[category as keyof typeof TOOL_CATEGORIES];
  const statusColor = toolCall.status === "success"
    ? "var(--sapPositiveColor)"
    : toolCall.status === "error"
    ? "var(--sapNegativeColor)"
    : "var(--color-text-secondary)";

  return (
    <div className="tool-call-card">
      {/* Header - always visible */}
      <div onClick={() => setExpanded(!expanded)} className="tool-call-card__header">
        <Icon name={expanded ? "navigation-down-arrow" : "navigation-right-arrow"} style={{ fontSize: 10, color: "var(--color-text-secondary)", flexShrink: 0 }} />
        <span
          className="tool-call-card__category-dot"
          style={{ background: catMeta?.color ?? "var(--color-text-secondary)" }}
        />
        <span className="tool-call-card__title">
          {toolCall.name}
        </span>
        <span className="tool-call-card__category">
          {catMeta?.label}
        </span>
        <span className="tool-call-card__meta">
          {toolCall.duration !== undefined && (
            <span className="tool-call-card__duration">
              {toolCall.duration}ms
            </span>
          )}
          <span className="tool-call-card__status-dot" style={{ background: statusColor }} />
        </span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="tool-call-card__body">
          {/* Parameters */}
          <div className="tool-call-card__section">
            <div className="tool-call-card__label">
              Parameters
            </div>
            <pre className="sap-code-block" style={{ maxHeight: 200, overflowY: "auto", margin: 0 }}>
              {JSON.stringify(toolCall.parameters, null, 2)}
            </pre>
          </div>

          {/* Result */}
          {toolCall.result !== undefined && (
            <div className="tool-call-card__section tool-call-card__section--result">
              <div className="tool-call-card__label">
                Result
              </div>
              <pre className="sap-code-block" style={{ maxHeight: 400, overflowY: "auto", margin: 0, color: toolCall.status === "error" ? "var(--sapNegativeColor)" : undefined }}>
                {typeof toolCall.result === "string" ? toolCall.result : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
