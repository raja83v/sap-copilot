import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "convex/react";
import { Button, Icon } from "@ui5/webcomponents-react";
import {
  AGENT_ROLE_LABELS,
  WORKFLOW_PHASE_LABELS,
  WORKFLOW_TYPE_LABELS,
  type Workflow,
  type WorkflowApproval,
  type WorkflowStep,
  type WorkflowType,
} from "@sap-copilot/shared";
import { api } from "../../../../../convex/_generated/api";
import type { Id } from "../../../../../convex/_generated/dataModel";
import { resumeWorkflow } from "@/lib/gateway";
import { useAppStore } from "@/stores/appStore";
import { ApprovalPanel } from "./ApprovalPanel";
import { AgentActivityFeed } from "./AgentActivityFeed";
import { ArtifactsViewer } from "./ArtifactsViewer";
import { WorkflowGraph } from "./WorkflowGraph";
import { WorkflowHistory } from "./WorkflowHistory";

interface WorkflowWorkspacePageProps {
  onStartWorkflow: (type: string) => void;
}

type WorkspaceTemplate = {
  type: WorkflowType;
  title: string;
  description: string;
  action: string;
};

interface SapSystemSummary {
  _id: string;
  name: string;
  description?: string;
  client: string;
}

const WORKSPACE_TEMPLATES: WorkspaceTemplate[] = [
  {
    type: "create_class",
    title: "Create ABAP Class",
    description: "Create a new ABAP class, validate it, and prepare transport-ready source.",
    action: "create",
  },
  {
    type: "enhance_object",
    title: "Modify Existing ABAP Class",
    description: "Update an existing ABAP class with validated implementation changes.",
    action: "update",
  },
  {
    type: "create_cds_view",
    title: "Create CDS View",
    description: "Generate a CDS object and run the workflow checks needed before activation.",
    action: "create",
  },
  {
    type: "code_review",
    title: "Quality Remediation",
    description: "Run repository analysis and quality remediation against an existing object.",
    action: "update",
  },
  {
    type: "transport_management",
    title: "Promote to QA",
    description: "Prepare a transport, release it with approvals, and move the change forward.",
    action: "update",
  },
];

const OBJECT_TYPE_LABELS: Partial<Record<WorkflowType, string>> = {
  create_class: "ABAP_CLASS",
  enhance_object: "ABAP_CLASS",
  create_cds_view: "CDS_VIEW",
  create_function_module: "FUNCTION_MODULE",
  create_table: "TABLE",
  create_data_element: "DATA_ELEMENT",
  create_interface: "ABAP_INTERFACE",
  create_rap_bo: "RAP_BUSINESS_OBJECT",
  create_ui5_app: "UI5_APP",
  code_review: "ABAP_OBJECT",
  refactor_object: "ABAP_OBJECT",
  transport_management: "TRANSPORT",
  documentation: "ABAP_DOCUMENTATION",
  migration: "ABAP_OBJECT",
  test_creation: "ABAP_UNIT_TEST",
  amdp_creation: "AMDP_CLASS",
};

function parseJson<T>(value?: string): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

function formatDateTime(value?: number): string {
  if (!value) return "No timestamp";
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDateRange(start?: number, end?: number): string {
  if (!start) return "No timestamps recorded.";
  return `${formatDateTime(start)} to ${formatDateTime(end ?? start)}`;
}

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function extractObjectName(workflow: Workflow): string {
  const metadata = parseJson<Record<string, unknown>>(workflow.metadata) ?? {};
  const artifactMap = parseJson<Record<string, string>>(workflow.artifacts) ?? {};

  const metadataKeys = [
    "object_name",
    "objectName",
    "class_name",
    "className",
    "name",
    "cds_name",
    "table_name",
  ];

  for (const key of metadataKeys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }

  const artifactName = Object.keys(artifactMap)[0];
  if (artifactName) return artifactName;

  const userRequestMatch = workflow.userRequest.match(/\b[A-Z][A-Z0-9_]{3,}\b/);
  if (userRequestMatch) return userRequestMatch[0];

  return "Object pending";
}

function getObjectTypeLabel(workflow: Workflow): string {
  const metadata = parseJson<Record<string, unknown>>(workflow.metadata) ?? {};
  const fromMetadata = metadata.object_type ?? metadata.objectType ?? metadata.type;
  if (typeof fromMetadata === "string" && fromMetadata.trim()) return fromMetadata.trim().toUpperCase();
  return OBJECT_TYPE_LABELS[workflow.type] ?? "ABAP_OBJECT";
}

function getStatusClass(status: Workflow["phase"] | WorkflowStep["status"]): string {
  if (status === "completed") return "workflow-status-pill workflow-status-pill--success";
  if (status === "failed") return "workflow-status-pill workflow-status-pill--danger";
  if (status === "paused") return "workflow-status-pill workflow-status-pill--warning";
  return "workflow-status-pill workflow-status-pill--neutral";
}

function getPriorityLabel(step: WorkflowStep): "LOW" | "MEDIUM" | "HIGH" {
  if (step.status === "failed") return "HIGH";
  if ((step.toolCalls?.length ?? 0) > 0 || step.agent === "coder" || step.agent === "tester") return "MEDIUM";
  return "LOW";
}

function getStepSummary(step: WorkflowStep): string {
  if (step.result?.trim()) return step.result.trim();
  if (step.status === "failed") return "This stage failed before a detailed message was captured.";
  if (step.toolCalls?.length) return `${step.toolCalls.length} tool call${step.toolCalls.length === 1 ? "" : "s"} executed during this stage.`;
  return "No step messages captured.";
}

function getCreatedObjects(workflow: Workflow): string[] {
  const metadata = parseJson<Record<string, unknown>>(workflow.metadata) ?? {};
  const createdObjects = metadata.created_objects;
  if (Array.isArray(createdObjects)) {
    return createdObjects.filter((value): value is string => typeof value === "string" && value.trim().length > 0);
  }
  return [];
}

const WORKFLOW_DETAIL_TABS = ["overview", "activity", "plan", "artifacts", "history"] as const;

const WORKFLOW_CALLBACKS = {
  onWorkflowStart: () => {},
  onAgentStart: () => {},
  onAgentEnd: () => {},
  onContent: () => {},
  onToolStart: () => {},
  onToolEnd: () => {},
  onApprovalRequired: () => {},
  onWorkflowPaused: () => {},
  onWorkflowResumed: () => {},
  onWorkflowComplete: () => {},
  onError: () => {},
};

function mapWorkflows(rawWorkflows: any[]): Workflow[] {
  return rawWorkflows.map((workflow) => ({
    id: workflow._id,
    sessionId: workflow.sessionId,
    systemId: workflow.systemId,
    type: workflow.type,
    status: workflow.status,
    phase: workflow.phase,
    userRequest: workflow.userRequest,
    plan: workflow.plan,
    artifacts: workflow.artifacts,
    metadata: workflow.metadata,
    approvals: (workflow.approvals ?? []) as WorkflowApproval[],
    steps: (workflow.steps ?? []) as WorkflowStep[],
    error: workflow.error,
    createdAt: workflow.createdAt,
    updatedAt: workflow.updatedAt,
  }));
}

export function WorkflowWorkspacePage({ onStartWorkflow }: WorkflowWorkspacePageProps) {
  const navigate = useNavigate();
  const { id: routeWorkflowId } = useParams();
  const {
    activeSystemId,
    activeWorkflowAgent,
    activeWorkflowId,
    activeWorkflowTab,
    setActiveWorkflow,
    setActiveWorkflowTab,
  } = useAppStore();

  const system = useQuery(
    api.systems.get,
    activeSystemId ? { id: activeSystemId as Id<"systems"> } : "skip",
  ) as SapSystemSummary | null | undefined;
  const rawWorkflows = (useQuery(
    api.workflows.listBySystem,
    activeSystemId ? { systemId: activeSystemId as Id<"systems"> } : "skip",
  ) ?? []) as any[];
  const approvalCount = useQuery(
    api.workflows.countPendingApprovals,
    activeSystemId ? { systemId: activeSystemId as Id<"systems"> } : "skip",
  );

  const workflows = mapWorkflows(rawWorkflows).sort((left, right) => right.updatedAt - left.updatedAt);
  const selectedWorkflow =
    workflows.find((workflow) => workflow.id === routeWorkflowId) ??
    workflows.find((workflow) => workflow.id === activeWorkflowId) ??
    workflows[0] ??
    null;

  useEffect(() => {
    if (routeWorkflowId && routeWorkflowId !== activeWorkflowId) {
      setActiveWorkflow(routeWorkflowId);
    }
  }, [routeWorkflowId, activeWorkflowId, setActiveWorkflow]);

  useEffect(() => {
    if (!routeWorkflowId && selectedWorkflow && selectedWorkflow.id !== activeWorkflowId) {
      setActiveWorkflow(selectedWorkflow.id);
    }
    if (!routeWorkflowId && !selectedWorkflow && activeWorkflowId) {
      setActiveWorkflow(null);
    }
  }, [routeWorkflowId, selectedWorkflow, activeWorkflowId, setActiveWorkflow]);

  const workflowTitle = selectedWorkflow
    ? WORKFLOW_TYPE_LABELS[selectedWorkflow.type] ?? titleCase(selectedWorkflow.type)
    : "No workflow selected";
  const workflowPhaseLabel = selectedWorkflow
    ? WORKFLOW_PHASE_LABELS[selectedWorkflow.phase] ?? titleCase(selectedWorkflow.phase)
    : "Awaiting selection";
  const objectName = selectedWorkflow ? extractObjectName(selectedWorkflow) : "Select a workflow run";
  const objectType = selectedWorkflow ? getObjectTypeLabel(selectedWorkflow) : "ABAP_OBJECT";
  const totalToolCalls = selectedWorkflow?.steps.reduce((count, step) => count + (step.toolCalls?.length ?? 0), 0) ?? 0;
  const pendingApproval = selectedWorkflow?.approvals.find((approval) => approval.status === "pending") ?? null;
  const currentWorkflowAgent = selectedWorkflow?.steps.find((step) => step.status === "running")?.agent ?? activeWorkflowAgent;
  const workflowDetailTab = WORKFLOW_DETAIL_TABS.includes(activeWorkflowTab) ? activeWorkflowTab : "overview";
  const hasWorkflows = workflows.length > 0;
  const headerApprovalLabel = (approvalCount ?? 0) === 0 ? "No approvals pending" : `${approvalCount} approvals pending`;

  return (
    <div className="workflow-workspace">
        <header className="workflow-workspace-header">
          <div className="workflow-workspace-header__copy">
            <div className="workflow-workspace-header__eyebrow">Workflow workspace</div>
            <h1 className="workflow-workspace-header__title">Workflows</h1>
            <div className="workflow-workspace-header__meta">
              <span className="workflow-header-chip">{system?.name ?? "No connected system"}</span>
              {system?.client && <span className="workflow-header-chip">Client {system.client}</span>}
              <span className="workflow-header-chip">{headerApprovalLabel}</span>
            </div>
          </div>
          <div className="workflow-workspace-header__actions">
            <Button design="Transparent" onClick={() => window.location.reload()}>
              Refresh
            </Button>
            <span className="workflow-environment-pill">{hasWorkflows ? `${workflows.length} runs` : "Ready"}</span>
          </div>
        </header>

        <div className={`workflow-workspace-grid ${!hasWorkflows ? "workflow-workspace-grid--empty" : ""}`}>
          <div className="workflow-workspace-stack">
            <section className="workflow-panel">
              <div className="workflow-panel__header">
                <div>
                  <h2 className="workflow-panel__title">Workflow runs</h2>
                </div>
                <span className="workflow-panel__count">{workflows.length} total</span>
              </div>

              <div className="workflow-run-list">
                {workflows.length === 0 ? (
                  <div className="workflow-empty-copy">No workflow runs yet for this tenant.</div>
                ) : (
                  workflows.map((workflow) => {
                    const isSelected = selectedWorkflow?.id === workflow.id;
                    return (
                      <button
                        key={workflow.id}
                        type="button"
                        className={`workflow-run-card ${isSelected ? "workflow-run-card--selected" : ""}`}
                        onClick={() => {
                          setActiveWorkflow(workflow.id);
                          navigate(`/workflows/${workflow.id}`);
                        }}
                      >
                        <div className="workflow-run-card__title-row">
                          <span className="workflow-run-card__title">
                            {WORKFLOW_TYPE_LABELS[workflow.type] ?? titleCase(workflow.type)}
                          </span>
                          <span className={getStatusClass(workflow.phase)}>{workflowPhaseLabelFor(workflow)}</span>
                        </div>
                        <div className="workflow-run-card__subtitle">
                          {system?.name ?? "sap-dev"} • {extractObjectName(workflow)}
                        </div>
                        <div className="workflow-run-card__meta">
                          Updated {formatDateTime(workflow.updatedAt)}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </section>

            <section className="workflow-panel">
              <div className="workflow-panel__header">
                <div>
                  <h2 className="workflow-panel__title">Start a new workflow</h2>
                  <p className="workflow-panel__description">Template</p>
                </div>
              </div>

              <div className="workflow-template-list">
                {WORKSPACE_TEMPLATES.map((template) => (
                  <button
                    key={template.type}
                    type="button"
                    className="workflow-template-card"
                    onClick={() => onStartWorkflow(template.type)}
                  >
                    <div className="workflow-template-card__body">
                      <div className="workflow-template-card__title">{template.title}</div>
                      <div className="workflow-template-card__description">{template.description}</div>
                    </div>
                    <span className="workflow-template-card__action">{template.action}</span>
                  </button>
                ))}
              </div>
            </section>
          </div>

          <section className="workflow-panel workflow-panel--detail">
            {selectedWorkflow ? (
              <>
                <div className="workflow-detail-header">
                  <div>
                    <h2 className="workflow-detail-header__title">{workflowTitle}</h2>
                    <p className="workflow-detail-header__description">{selectedWorkflow.userRequest}</p>
                  </div>
                  <div className="workflow-detail-header__status">
                    <span className={getStatusClass(selectedWorkflow.phase)}>{workflowPhaseLabel}</span>
                    <div className="workflow-detail-header__timestamp">Updated {formatDateTime(selectedWorkflow.updatedAt)}</div>
                  </div>
                </div>

                <div className="workflow-detail-meta">
                  <div className="workflow-detail-meta__item">
                    <span className="workflow-detail-meta__label">Landscape</span>
                    <span className="workflow-detail-meta__value">{system?.name ?? "sap-dev"}</span>
                  </div>
                  <div className="workflow-detail-meta__item">
                    <span className="workflow-detail-meta__label">Object type</span>
                    <span className="workflow-detail-meta__value">{objectType}</span>
                  </div>
                  <div className="workflow-detail-meta__item workflow-detail-meta__item--wide">
                    <span className="workflow-detail-meta__label">Object name</span>
                    <span className="workflow-detail-meta__value">{objectName}</span>
                  </div>
                </div>

                {(selectedWorkflow.error || selectedWorkflow.approvals.some((approval) => approval.status === "pending")) && (
                  <div className="workflow-alert-strip">
                    {selectedWorkflow.error
                      ? selectedWorkflow.error
                      : `${selectedWorkflow.approvals.filter((approval) => approval.status === "pending").length} approval gate${selectedWorkflow.approvals.filter((approval) => approval.status === "pending").length === 1 ? " is" : "s are"} waiting for action.`}
                  </div>
                )}

                <div className="workflow-summary-row">
                  <div className="workflow-summary-chip">
                    <span className="workflow-summary-chip__label">Steps</span>
                    <span className="workflow-summary-chip__value">{selectedWorkflow.steps.length}</span>
                  </div>
                  <div className="workflow-summary-chip">
                    <span className="workflow-summary-chip__label">Tool calls</span>
                    <span className="workflow-summary-chip__value">{totalToolCalls}</span>
                  </div>
                  <div className="workflow-summary-chip">
                    <span className="workflow-summary-chip__label">Approvals</span>
                    <span className="workflow-summary-chip__value">{selectedWorkflow.approvals.length}</span>
                  </div>
                </div>

                <div className="workflow-detail-tabs" role="tablist" aria-label="Workflow detail sections">
                  {WORKFLOW_DETAIL_TABS.map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      role="tab"
                      aria-selected={workflowDetailTab === tab}
                      className={`workflow-detail-tab ${workflowDetailTab === tab ? "workflow-detail-tab--active" : ""}`}
                      onClick={() => setActiveWorkflowTab(tab)}
                    >
                      {titleCase(tab)}
                    </button>
                  ))}
                </div>

                <div className="workflow-detail-body">
                  {workflowDetailTab === "overview" && (
                    <div className="workflow-detail-section-stack">
                      {pendingApproval && (
                        <ApprovalPanel
                          approval={pendingApproval}
                          onApprove={() => resumeWorkflow(selectedWorkflow.id, true, "", WORKFLOW_CALLBACKS)}
                          onReject={(feedback) => resumeWorkflow(selectedWorkflow.id, false, feedback, WORKFLOW_CALLBACKS)}
                        />
                      )}

                      <div className="workflow-stage-panel">
                        <div className="workflow-stage-panel__header">Execution graph</div>
                        <div className="workflow-graph-card">
                          <WorkflowGraph
                            workflowType={selectedWorkflow.type}
                            currentNode={currentWorkflowAgent}
                            completedNodes={selectedWorkflow.steps.filter((step) => step.status === "completed").map((step) => step.agent)}
                            failedNodes={selectedWorkflow.steps.filter((step) => step.status === "failed").map((step) => step.agent)}
                          />
                        </div>
                      </div>

                      <div className="workflow-stage-panel">
                        <div className="workflow-stage-panel__header">Stage timeline</div>
                        <div className="workflow-stage-list">
                          {selectedWorkflow.steps.length === 0 ? (
                            <div className="workflow-empty-copy">No stage events recorded yet.</div>
                          ) : (
                            [...selectedWorkflow.steps]
                              .sort((left, right) => left.startedAt - right.startedAt)
                              .map((step) => {
                                const priority = getPriorityLabel(step);
                                return (
                                  <div key={step.id} className="workflow-stage-item">
                                    <div className={`workflow-stage-item__dot workflow-stage-item__dot--${step.status}`} />
                                    <div className="workflow-stage-item__content">
                                      <div className="workflow-stage-item__title-row">
                                        <div>
                                          <div className="workflow-stage-item__title">{step.action}</div>
                                          <div className="workflow-stage-item__agent">{AGENT_ROLE_LABELS[step.agent]} Agent</div>
                                        </div>
                                        <div className="workflow-stage-item__badges">
                                          <span className="workflow-stage-item__priority">{priority}</span>
                                          <span className="workflow-stage-item__state">{step.status.toUpperCase()}</span>
                                        </div>
                                      </div>
                                      <div className="workflow-stage-item__summary">{getStepSummary(step)}</div>
                                      <div className="workflow-stage-item__time">{formatDateRange(step.startedAt, step.completedAt)}</div>
                                    </div>
                                  </div>
                                );
                              })
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {workflowDetailTab === "activity" && (
                    <div className="workflow-detail-section-card">
                      <div className="workflow-detail-section-card__header">Agent activity</div>
                      <AgentActivityFeed steps={selectedWorkflow.steps} currentAgent={currentWorkflowAgent} />
                    </div>
                  )}

                  {workflowDetailTab === "plan" && (
                    <div className="workflow-detail-section-card">
                      <div className="workflow-detail-section-card__header">Execution plan</div>
                      {selectedWorkflow.plan?.trim() ? (
                        <pre className="workflow-plan-block">{selectedWorkflow.plan}</pre>
                      ) : (
                        <div className="workflow-empty-copy">No plan was captured for this workflow run.</div>
                      )}
                    </div>
                  )}

                  {workflowDetailTab === "artifacts" && (
                    <div className="workflow-detail-section-card workflow-detail-section-card--fill">
                      <div className="workflow-detail-section-card__header">Artifacts and created objects</div>
                      <ArtifactsViewer
                        artifacts={selectedWorkflow.artifacts}
                        createdObjects={getCreatedObjects(selectedWorkflow)}
                      />
                    </div>
                  )}

                  {workflowDetailTab === "history" && (
                    <div className="workflow-detail-section-card">
                      <div className="workflow-detail-section-card__header">Workflow history</div>
                      <WorkflowHistory
                        steps={selectedWorkflow.steps}
                        approvals={selectedWorkflow.approvals}
                        createdAt={selectedWorkflow.createdAt}
                      />
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="workflow-detail-empty">
                <Icon name="workflow-tasks" style={{ fontSize: 42, opacity: 0.45 }} />
                <h2 className="workflow-detail-empty__title">
                  {hasWorkflows ? "No workflow selected" : "Ready to start a workflow"}
                </h2>
                <p className="workflow-detail-empty__copy">
                  {hasWorkflows
                    ? "Select a workflow run from the left column to inspect progress, approvals, and artifacts."
                    : "Choose a template from the left to launch an orchestration against the connected SAP system."}
                </p>
                {!hasWorkflows && system && (
                  <div className="workflow-detail-empty__meta">
                    <span className="workflow-header-chip">{system.name}</span>
                    <span className="workflow-header-chip">Client {system.client}</span>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
    </div>
  );
}

function workflowPhaseLabelFor(workflow: Workflow): string {
  return WORKFLOW_PHASE_LABELS[workflow.phase] ?? titleCase(workflow.phase);
}