import type { WorkflowStep, AgentRole } from "@sap-copilot/shared";
import { AGENT_ROLE_LABELS } from "@sap-copilot/shared";

interface AgentActivityFeedProps {
  steps: WorkflowStep[];
  currentAgent: string | null;
}

const AGENT_ICONS: Record<AgentRole, string> = {
  planner: "📋",
  clarifier: "❓",
  coder: "💻",
  reviewer: "🔍",
  tester: "🧪",
  activator: "🚀",
  analyzer: "📊",
  documenter: "📝",
  migrator: "📦",
};

const STATUS_COLORS: Record<string, string> = {
  running: "#3b82f6",
  completed: "#22c55e",
  failed: "#ef4444",
  skipped: "#9ca3af",
};

export function AgentActivityFeed({ steps, currentAgent }: AgentActivityFeedProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {steps.length === 0 && !currentAgent && (
        <div style={{ padding: 20, textAlign: "center", color: "var(--sapContent_LabelColor)", fontSize: 13 }}>
          No activity yet. The workflow will start processing shortly.
        </div>
      )}

      {steps.map((step, i) => (
        <div
          key={step.id}
          style={{
            display: "flex",
            gap: 10,
            padding: "8px 0",
            borderBottom: i < steps.length - 1 ? "1px solid var(--sapGroup_ContentBorderColor)" : "none",
          }}
        >
          {/* Timeline indicator */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 24, flexShrink: 0 }}>
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: STATUS_COLORS[step.status] ?? "#9ca3af",
                border: step.status === "running" ? "2px solid #93c5fd" : "none",
                animation: step.status === "running" ? "pulse 1.5s infinite" : "none",
              }}
            />
            {i < steps.length - 1 && (
              <div style={{
                width: 2,
                flex: 1,
                minHeight: 16,
                background: "var(--sapGroup_ContentBorderColor)",
              }} />
            )}
          </div>

          {/* Content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Agent + Action */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 14 }}>
                {AGENT_ICONS[step.agent as AgentRole] ?? "🤖"}
              </span>
              <span style={{ fontWeight: 600, fontSize: 12, color: "var(--sapTextColor)" }}>
                {AGENT_ROLE_LABELS[step.agent as AgentRole] ?? step.agent}
              </span>
              <span style={{
                fontSize: 10,
                padding: "1px 6px",
                borderRadius: 8,
                background: STATUS_COLORS[step.status] ?? "#9ca3af",
                color: "#fff",
                fontWeight: 600,
              }}>
                {step.status}
              </span>
              {step.startedAt && (
                <span style={{ fontSize: 10, color: "var(--sapContent_LabelColor)", marginLeft: "auto" }}>
                  {new Date(step.startedAt).toLocaleTimeString()}
                </span>
              )}
            </div>

            {/* Action description */}
            <div style={{ fontSize: 12, color: "var(--sapContent_LabelColor)", marginBottom: 4 }}>
              {step.action}
            </div>

            {/* Result preview */}
            {step.result && (
              <div style={{
                fontSize: 11,
                color: "var(--sapTextColor)",
                padding: "6px 10px",
                borderRadius: 6,
                background: "var(--sapList_Background)",
                border: "1px solid var(--sapGroup_ContentBorderColor)",
                maxHeight: 80,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "pre-wrap",
                lineHeight: 1.5,
              }}>
                {step.result.slice(0, 300)}
                {step.result.length > 300 && "..."}
              </div>
            )}

            {/* Tool calls summary */}
            {step.toolCalls && step.toolCalls.length > 0 && (
              <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
                {step.toolCalls.map((tc, j) => (
                  <span
                    key={j}
                    style={{
                      fontSize: 10,
                      padding: "2px 6px",
                      borderRadius: 6,
                      background: tc.status === "success" ? "var(--sapPositiveBackground)" : "var(--sapErrorBackground)",
                      color: tc.status === "success" ? "var(--sapPositiveColor)" : "var(--sapNegativeColor)",
                      fontWeight: 500,
                    }}
                  >
                    🔧 {tc.name}
                    {tc.duration ? ` (${tc.duration}ms)` : ""}
                  </span>
                ))}
              </div>
            )}

            {/* Duration */}
            {step.completedAt && step.startedAt && (
              <div style={{ fontSize: 10, color: "var(--sapContent_LabelColor)", marginTop: 4 }}>
                Duration: {((step.completedAt - step.startedAt) / 1000).toFixed(1)}s
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Current agent indicator */}
      {currentAgent && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 0",
          color: "var(--sapInformationColor)",
          fontSize: 12,
        }}>
          <div style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "#3b82f6",
            animation: "pulse 1.5s infinite",
          }} />
          <span style={{ fontSize: 14 }}>
            {AGENT_ICONS[currentAgent as AgentRole] ?? "🤖"}
          </span>
          <span style={{ fontWeight: 600 }}>
            {AGENT_ROLE_LABELS[currentAgent as AgentRole] ?? currentAgent}
          </span>
          <span>is working...</span>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
