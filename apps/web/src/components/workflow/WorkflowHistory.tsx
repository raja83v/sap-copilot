import { useState } from "react";
import type { WorkflowStep, WorkflowApproval, AgentRole } from "@sap-copilot/shared";
import { AGENT_ROLE_LABELS } from "@sap-copilot/shared";

interface WorkflowHistoryProps {
  steps: WorkflowStep[];
  approvals: WorkflowApproval[];
  createdAt: number;
}

type HistoryEntry = {
  type: "step" | "approval";
  timestamp: number;
  data: WorkflowStep | WorkflowApproval;
};

const AGENT_ICONS: Record<string, string> = {
  planner: "📋", clarifier: "❓", coder: "💻", reviewer: "🔍",
  tester: "🧪", activator: "🚀", analyzer: "📊", documenter: "📝", migrator: "📦",
};

export function WorkflowHistory({ steps, approvals, createdAt }: WorkflowHistoryProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "steps" | "approvals">("all");

  // Merge steps and approvals into a timeline
  const entries: HistoryEntry[] = [
    ...steps.map((s) => ({
      type: "step" as const,
      timestamp: s.startedAt,
      data: s,
    })),
    ...approvals.map((a) => ({
      type: "approval" as const,
      timestamp: a.requestedAt,
      data: a,
    })),
  ].sort((a, b) => a.timestamp - b.timestamp);

  const filtered = entries.filter((e) => {
    if (filter === "steps") return e.type === "step";
    if (filter === "approvals") return e.type === "approval";
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 4 }}>
        {(["all", "steps", "approvals"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "4px 12px",
              borderRadius: 12,
              border: filter === f ? "2px solid var(--sapButton_Emphasized_Background)" : "1px solid var(--sapButton_BorderColor)",
              background: filter === f ? "var(--sapButton_Emphasized_Background)" : "transparent",
              color: filter === f ? "var(--sapButton_Emphasized_TextColor)" : "var(--sapTextColor)",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {f === "all" ? `All (${entries.length})` : f === "steps" ? `Steps (${steps.length})` : `Approvals (${approvals.length})`}
          </button>
        ))}
      </div>

      {/* Timeline header */}
      <div style={{ fontSize: 11, color: "var(--sapContent_LabelColor)" }}>
        Workflow started: {new Date(createdAt).toLocaleString()}
      </div>

      {/* Timeline entries */}
      {filtered.map((entry, i) => {
        const isStep = entry.type === "step";
        const step = isStep ? (entry.data as WorkflowStep) : null;
        const approval = !isStep ? (entry.data as WorkflowApproval) : null;
        const id = step?.id ?? approval?.id ?? String(i);
        const isExpanded = expandedId === id;

        return (
          <div
            key={id}
            onClick={() => setExpandedId(isExpanded ? null : id)}
            style={{
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid var(--sapGroup_ContentBorderColor)",
              background: "var(--sapGroup_ContentBackground)",
              cursor: "pointer",
              transition: "border-color 0.15s",
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, transform: isExpanded ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>
                ▶
              </span>
              {isStep && step ? (
                <>
                  <span>{AGENT_ICONS[step.agent] ?? "🤖"}</span>
                  <span style={{ fontWeight: 600, fontSize: 12, color: "var(--sapTextColor)" }}>
                    {AGENT_ROLE_LABELS[step.agent as AgentRole] ?? step.agent}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--sapContent_LabelColor)" }}>
                    {step.action}
                  </span>
                  <span style={{
                    marginLeft: "auto",
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 8,
                    background: step.status === "completed" ? "#22c55e" : step.status === "failed" ? "#ef4444" : "#3b82f6",
                    color: "#fff",
                    fontWeight: 600,
                  }}>
                    {step.status}
                  </span>
                </>
              ) : approval ? (
                <>
                  <span>✋</span>
                  <span style={{ fontWeight: 600, fontSize: 12, color: "var(--sapTextColor)" }}>
                    Approval Gate
                  </span>
                  <span style={{ fontSize: 11, color: "var(--sapContent_LabelColor)" }}>
                    Phase: {approval.phase}
                  </span>
                  <span style={{
                    marginLeft: "auto",
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 8,
                    background: approval.status === "approved" ? "#22c55e" : approval.status === "rejected" ? "#ef4444" : "#f59e0b",
                    color: "#fff",
                    fontWeight: 600,
                  }}>
                    {approval.status}
                  </span>
                </>
              ) : null}
              <span style={{ fontSize: 10, color: "var(--sapContent_LabelColor)" }}>
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
            </div>

            {/* Expanded details */}
            {isExpanded && (
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--sapGroup_ContentBorderColor)" }}>
                {isStep && step ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {step.result && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--sapContent_LabelColor)", marginBottom: 4 }}>Result:</div>
                        <div style={{
                          fontSize: 11,
                          padding: 10,
                          borderRadius: 6,
                          background: "var(--sapList_Background)",
                          whiteSpace: "pre-wrap",
                          maxHeight: 200,
                          overflow: "auto",
                          lineHeight: 1.5,
                          color: "var(--sapTextColor)",
                        }}>
                          {step.result}
                        </div>
                      </div>
                    )}
                    {step.toolCalls && step.toolCalls.length > 0 && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--sapContent_LabelColor)", marginBottom: 4 }}>
                          Tool Calls ({step.toolCalls.length}):
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {step.toolCalls.map((tc, j) => (
                            <div key={j} style={{
                              fontSize: 11,
                              padding: "4px 8px",
                              borderRadius: 4,
                              background: "var(--sapList_Background)",
                              display: "flex",
                              justifyContent: "space-between",
                              color: "var(--sapTextColor)",
                            }}>
                              <span>🔧 {tc.name}</span>
                              <span style={{ color: "var(--sapContent_LabelColor)" }}>
                                {tc.status} · {tc.duration}ms
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {step.completedAt && step.startedAt && (
                      <div style={{ fontSize: 10, color: "var(--sapContent_LabelColor)" }}>
                        Duration: {((step.completedAt - step.startedAt) / 1000).toFixed(1)}s
                      </div>
                    )}
                  </div>
                ) : approval ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{
                      fontSize: 11,
                      padding: 10,
                      borderRadius: 6,
                      background: "var(--sapList_Background)",
                      whiteSpace: "pre-wrap",
                      maxHeight: 200,
                      overflow: "auto",
                      color: "var(--sapTextColor)",
                    }}>
                      {approval.details}
                    </div>
                    {approval.feedback && (
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--sapContent_LabelColor)", marginBottom: 4 }}>Feedback:</div>
                        <div style={{ fontSize: 11, color: "var(--sapTextColor)" }}>{approval.feedback}</div>
                      </div>
                    )}
                    {approval.respondedAt && (
                      <div style={{ fontSize: 10, color: "var(--sapContent_LabelColor)" }}>
                        Responded: {new Date(approval.respondedAt).toLocaleString()}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            )}
          </div>
        );
      })}

      {filtered.length === 0 && (
        <div style={{ padding: 20, textAlign: "center", color: "var(--sapContent_LabelColor)", fontSize: 13 }}>
          No history entries yet.
        </div>
      )}
    </div>
  );
}
