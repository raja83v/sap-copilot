import { BusyIndicator } from "@ui5/webcomponents-react";
import { useAppStore } from "@/stores/appStore";
import type { WorkflowAgentStep } from "@/stores/appStore";

const AGENT_LABELS: Record<string, string> = {
  clarifier: "Clarifying",
  planner: "Planning",
  coder: "Coding",
  reviewer: "Reviewing",
  tester: "Testing",
  activator: "Activating",
  analyzer: "Analyzing",
  documenter: "Documenting",
  migrator: "Migrating",
};

const AGENT_ICONS: Record<string, string> = {
  clarifier: "❓",
  planner: "📋",
  coder: "💻",
  reviewer: "🔍",
  tester: "🧪",
  activator: "🚀",
  analyzer: "📊",
  documenter: "📝",
  migrator: "📦",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--sapContent_LabelColor)",
  running: "var(--sapInformationColor)",
  completed: "var(--sapPositiveColor)",
  failed: "var(--sapNegativeColor)",
};

function StepDot({ step }: { step: WorkflowAgentStep }) {
  const isRunning = step.status === "running";
  const color = STATUS_COLORS[step.status] || STATUS_COLORS.pending;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        minWidth: 72,
        position: "relative",
      }}
    >
      {/* Dot / spinner */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
          background: step.status === "completed"
            ? "var(--sapPositiveBackground)"
            : step.status === "running"
              ? "var(--sapInformationBackground)"
              : step.status === "failed"
                ? "var(--sapErrorBackground)"
                : "var(--sapList_Background)",
          border: `2px solid ${color}`,
          transition: "all 0.3s ease",
          ...(isRunning ? { animation: "pulse 1.5s infinite" } : {}),
        }}
      >
        {step.status === "completed" ? "✓" : step.status === "failed" ? "✗" : AGENT_ICONS[step.agent] || "⚙️"}
      </div>
      {/* Label */}
      <span
        style={{
          fontSize: 11,
          fontWeight: isRunning ? 700 : 500,
          color: isRunning ? "var(--sapInformationColor)" : color,
          textAlign: "center",
          whiteSpace: "nowrap",
        }}
      >
        {AGENT_LABELS[step.agent] || step.agent}
      </span>
      {/* Tool calls badge */}
      {step.status === "completed" && step.toolCalls != null && step.toolCalls > 0 && (
        <span style={{ fontSize: 9, color: "var(--sapContent_LabelColor)" }}>
          {step.toolCalls} tools
        </span>
      )}
    </div>
  );
}

function StepConnector({ completed }: { completed: boolean }) {
  return (
    <div
      style={{
        flex: 1,
        height: 2,
        minWidth: 20,
        maxWidth: 48,
        background: completed
          ? "var(--sapPositiveColor)"
          : "var(--sapGroup_ContentBorderColor)",
        alignSelf: "flex-start",
        marginTop: 16,
        transition: "background 0.3s ease",
      }}
    />
  );
}

/**
 * Workflow progress stepper shown in the chat during workflow execution.
 * Renders a horizontal stepper with agent dots + connectors.
 */
export function WorkflowProgress() {
  const { workflowSteps, activeWorkflowAgent, workflowStreamingContent } = useAppStore();

  if (workflowSteps.length === 0) return null;

  const currentAgent = activeWorkflowAgent;

  return (
    <div
      style={{
        alignSelf: "flex-start",
        maxWidth: "90%",
        border: "1px solid var(--sapGroup_ContentBorderColor)",
        borderRadius: 12,
        background: "var(--sapGroup_ContentBackground)",
        padding: "16px 20px 12px",
        marginBottom: 4,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "var(--sapTextColor)" }}>
          Workflow Progress
        </span>
        {currentAgent && (
          <span
            style={{
              fontSize: 11,
              padding: "2px 8px",
              borderRadius: 10,
              background: "var(--sapInformationBackground)",
              color: "var(--sapInformationColor)",
              fontWeight: 600,
            }}
          >
            {AGENT_LABELS[currentAgent] || currentAgent}...
          </span>
        )}
      </div>

      {/* Stepper */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 0, overflowX: "auto", paddingBottom: 4 }}>
        {workflowSteps.map((step: WorkflowAgentStep, i: number) => (
          <div key={step.agent} style={{ display: "flex", alignItems: "flex-start" }}>
            <StepDot step={step} />
            {i < workflowSteps.length - 1 && (
              <StepConnector completed={step.status === "completed"} />
            )}
          </div>
        ))}
      </div>

      {/* Live streaming content from current agent */}
      {currentAgent && workflowStreamingContent && (
        <div
          style={{
            marginTop: 12,
            padding: "8px 12px",
            borderRadius: 8,
            background: "var(--sapList_Background)",
            border: "1px solid var(--sapGroup_ContentBorderColor)",
            fontSize: 13,
            color: "var(--sapTextColor)",
            maxHeight: 120,
            overflow: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            lineHeight: 1.5,
          }}
        >
          {workflowStreamingContent}
        </div>
      )}

      {/* Busy indicator for running agent */}
      {currentAgent && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
          <BusyIndicator active size="S" />
          <span style={{ fontSize: 12, color: "var(--sapContent_LabelColor)" }}>
            {AGENT_ICONS[currentAgent] || "⚙️"} {AGENT_LABELS[currentAgent] || currentAgent} agent is working...
          </span>
        </div>
      )}

      {/* Pulse animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.08); }
        }
      `}</style>
    </div>
  );
}
