// ─── SAP System ───

export interface SapSystem {
  id: string;
  userId: string;
  name: string;
  description: string;
  baseUrl: string;
  client: string;
  language: string;
  username: string; // encrypted
  password: string; // encrypted
  insecure: boolean;
  mode: ToolMode;
  safetyConfig: SafetyConfig;
  featureConfig: FeatureConfig;
  color: string;
  icon: string;
  status: SystemStatus;
  lastConnected?: number;
}

export type SystemStatus = "connected" | "disconnected" | "connecting" | "error";
export type ToolMode = "focused" | "expert";
export type UserRole = "admin" | "developer" | "viewer";

export interface SafetyConfig {
  readOnly: boolean;
  blockFreeSql: boolean;
  allowedOps: string;
  disallowedOps: string;
  allowedPackages: string[];
  allowTransportableEdits: boolean;
}

export interface FeatureConfig {
  abapgit: FeatureMode;
  rap: FeatureMode;
  amdp: FeatureMode;
  ui5: FeatureMode;
  transport: FeatureMode;
}

export type FeatureMode = "auto" | "on" | "off";

// ─── Chat ───

export interface ChatSession {
  id: string;
  userId: string;
  systemId: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  isArchived: boolean;
  messageCount: number;
  toolCallCount: number;
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  toolCallId?: string;
  timestamp: number;
  status?: MessageStatus;
  metadata?: MessageMetadata;
}

export type MessageRole = "user" | "assistant" | "system" | "tool";
export type MessageStatus = "pending" | "streaming" | "complete" | "error";

export interface ToolCall {
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  result?: string;
  duration?: number;
  status: "pending" | "running" | "success" | "error";
}

export interface MessageMetadata {
  model?: string;
  tokenCount?: number;
  latencyMs?: number;
}

// ─── Gateway API ───

export interface ChatRequest {
  systemId: string;
  sessionId: string;
  message: string;
  model?: string;
  conversationHistory?: ConversationMessage[];
}

export interface ConversationMessage {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  toolCallId?: string;
  toolCalls?: ToolCall[];
}

export interface ChatStreamEvent {
  type: "text" | "tool_call_start" | "tool_call_end" | "tool_result" | "error" | "done";
  data: string;
  toolCall?: ToolCall;
}

export interface SystemConnectRequest {
  baseUrl: string;
  client: string;
  username: string;
  password: string;
  insecure: boolean;
  mode: ToolMode;
  safetyConfig: SafetyConfig;
  featureConfig: FeatureConfig;
}

export interface SystemConnectionStatus {
  connected: boolean;
  uptime?: number;
  lastUsed?: number;
  processPid?: number;
  features?: Record<string, boolean>;
  systemInfo?: Record<string, string>;
}

export interface ToolInfo {
  name: string;
  description: string;
  category: ToolCategory;
  parameters: Record<string, ToolParameter>;
  operationCode: string;
}

export interface ToolParameter {
  type: string;
  description: string;
  required: boolean;
  default?: unknown;
}

// ─── User Preferences ───

export interface UserPreferences {
  theme: "dark" | "light" | "system";
  defaultSystemId?: string;
  defaultModel: string;
  autoActivate: boolean;
  showToolCalls: boolean;
  codeFont: string;
}

export type ToolCategory =
  | "read"
  | "search"
  | "crud"
  | "system"
  | "devtools"
  | "transport"
  | "diagnostics"
  | "codeintel"
  | "analysis"
  | "debug"
  | "report"
  | "git"
  | "ui5"
  | "amdp"
  | "install";

// ─── Workflows ───

export type WorkflowType =
  | "create_report"
  | "create_class"
  | "create_cds_view"
  | "create_function_module"
  | "create_table"
  | "create_data_element"
  | "create_interface"
  | "create_rap_bo"
  | "create_ui5_app"
  | "enhance_object"
  | "code_review"
  | "transport_management"
  | "debug_diagnose"
  | "refactor_object"
  | "performance_analysis"
  | "dump_analysis"
  | "mass_activation"
  | "git_operations"
  | "documentation"
  | "migration"
  | "test_creation"
  | "amdp_creation";

export type WorkflowPhase =
  | "planning"
  | "clarifying"
  | "coding"
  | "reviewing"
  | "testing"
  | "analyzing"
  | "documenting"
  | "migrating"
  | "activating"
  | "completed"
  | "failed"
  | "paused";

export type AgentRole =
  | "planner"
  | "clarifier"
  | "coder"
  | "reviewer"
  | "tester"
  | "activator"
  | "analyzer"
  | "documenter"
  | "migrator";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface WorkflowApproval {
  id: string;
  phase: string;
  status: ApprovalStatus;
  details: string;
  requestedAt: number;
  respondedAt?: number;
  feedback?: string;
}

export interface WorkflowStep {
  id: string;
  agent: AgentRole;
  action: string;
  status: "running" | "completed" | "failed" | "skipped";
  startedAt: number;
  completedAt?: number;
  result?: string;
  toolCalls?: ToolCall[];
}

export interface Workflow {
  id: string;
  sessionId: string;
  systemId: string;
  type: WorkflowType;
  status: string;
  phase: WorkflowPhase;
  userRequest: string;
  plan?: string;
  artifacts?: string;
  metadata?: string;
  approvals: WorkflowApproval[];
  steps: WorkflowStep[];
  error?: string;
  createdAt: number;
  updatedAt: number;
}

export type WorkflowCategory =
  | "creation"
  | "review"
  | "management"
  | "analysis"
  | "documentation";

// ─── Clarification ───

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "text" | "select" | "confirm";
  options?: string[];
  default?: string;
  required: boolean;
}

export interface ClarificationAnswer {
  id: string;
  answer: string;
}

// ─── Graph Visualization ───

export interface WorkflowGraphNode {
  id: string;
  type: "agent" | "approval" | "gate" | "internal";
  label: string;
  icon: string;
  description: string;
}

export interface WorkflowGraphEdge {
  from: string;
  to: string;
  condition?: string;
}

export interface WorkflowGraph {
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
  entry: string;
}

// ─── Workflow Template (for catalog) ───

export interface WorkflowTemplate {
  type: WorkflowType;
  description: string;
  category: WorkflowCategory;
  icon: string;
  agentCount: number;
  hasApprovalGates: boolean;
}

export const WORKFLOW_TYPE_LABELS: Record<WorkflowType, string> = {
  create_report: "Create Report",
  create_class: "Create Class",
  create_cds_view: "Create CDS View",
  create_function_module: "Create Function Module",
  create_table: "Create Table",
  create_data_element: "Create Data Element",
  create_interface: "Create Interface",
  create_rap_bo: "Create RAP Business Object",
  create_ui5_app: "Create UI5 App",
  enhance_object: "Enhance Object",
  code_review: "Code Review & Fix",
  transport_management: "Transport Management",
  debug_diagnose: "Debug & Diagnose",
  refactor_object: "Refactor Object",
  performance_analysis: "Performance Analysis",
  dump_analysis: "Dump Analysis",
  mass_activation: "Mass Activation",
  git_operations: "Git Operations",
  documentation: "Generate Documentation",
  migration: "Object Migration",
  test_creation: "Create Unit Tests",
  amdp_creation: "Create AMDP",
};

export const WORKFLOW_PHASE_LABELS: Record<WorkflowPhase, string> = {
  planning: "Planning",
  clarifying: "Clarifying",
  coding: "Coding",
  reviewing: "Reviewing",
  testing: "Testing",
  analyzing: "Analyzing",
  documenting: "Documenting",
  migrating: "Migrating",
  activating: "Activating",
  completed: "Completed",
  failed: "Failed",
  paused: "Awaiting Approval",
};

export const AGENT_ROLE_LABELS: Record<AgentRole, string> = {
  planner: "Planner",
  clarifier: "Clarifier",
  coder: "Coder",
  reviewer: "Reviewer",
  tester: "Tester",
  activator: "Activator",
  analyzer: "Analyzer",
  documenter: "Documenter",
  migrator: "Migrator",
};

export const WORKFLOW_CATEGORY_LABELS: Record<WorkflowCategory, string> = {
  creation: "Creation",
  review: "Review & Refactor",
  management: "Management",
  analysis: "Analysis & Debug",
  documentation: "Documentation",
};
