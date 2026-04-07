import { create } from "zustand";
import type { WorkflowApproval, ClarificationQuestion } from "@sap-copilot/shared";

// ─── Workflow agent step tracking ───
export interface WorkflowAgentStep {
  agent: string;
  status: "pending" | "running" | "completed" | "failed";
  phase?: string;
  toolCalls?: number;
  startedAt?: number;
  completedAt?: number;
}

// ─── App UI Store ───
interface AppState {
  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  // Context panel (right)
  contextPanelOpen: boolean;
  contextPanelTab: "explorer" | "code" | "details" | "history";
  toggleContextPanel: () => void;
  setContextPanelTab: (tab: AppState["contextPanelTab"]) => void;

  // Active system & session
  activeSystemId: string | null;
  activeSessionId: string | null;
  setActiveSystem: (id: string | null) => void;
  setActiveSession: (id: string | null) => void;

  // Chat
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;

  // Model selection
  selectedModel: string;
  setSelectedModel: (model: string) => void;

  // Trigger model list refresh (bump counter)
  modelRefreshKey: number;
  refreshModels: () => void;

  // Workflows
  activeWorkflowId: string | null;
  activeWorkflowAgent: string | null;
  activeWorkflowTab: "overview" | "activity" | "plan" | "artifacts" | "history";
  pendingApproval: (WorkflowApproval & { workflow_id: string }) | null;
  pendingClarification: {
    workflow_id: string;
    questions: ClarificationQuestion[];
  } | null;
  workflowNotifications: number;
  // Workflow progress tracking — ordered list of agent steps
  workflowSteps: WorkflowAgentStep[];
  workflowStreamingContent: string;
  setActiveWorkflow: (id: string | null) => void;
  setActiveWorkflowAgent: (agent: string | null) => void;
  setActiveWorkflowTab: (tab: AppState["activeWorkflowTab"]) => void;
  setPendingApproval: (approval: (WorkflowApproval & { workflow_id: string }) | null) => void;
  setPendingClarification: (clarification: AppState["pendingClarification"]) => void;
  setWorkflowNotifications: (count: number) => void;
  incrementWorkflowNotifications: () => void;
  // Workflow progress actions
  resetWorkflowProgress: () => void;
  addWorkflowStep: (agent: string) => void;
  completeWorkflowStep: (agent: string, phase?: string, toolCalls?: number) => void;
  failWorkflowStep: (agent: string) => void;
  appendWorkflowContent: (text: string) => void;
  setWorkflowStreamingContent: (content: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  contextPanelOpen: false,
  contextPanelTab: "explorer",
  toggleContextPanel: () => set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),
  setContextPanelTab: (tab) => set({ contextPanelTab: tab }),

  activeSystemId: null,
  activeSessionId: null,
  setActiveSystem: (id) => set({ activeSystemId: id, activeSessionId: null }),
  setActiveSession: (id) => set({ activeSessionId: id }),

  isStreaming: false,
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  selectedModel: "",
  setSelectedModel: (model) => set({ selectedModel: model }),

  modelRefreshKey: 0,
  refreshModels: () => set((s) => ({ modelRefreshKey: s.modelRefreshKey + 1 })),

  activeWorkflowId: null,
  activeWorkflowAgent: null,
  activeWorkflowTab: "overview",
  pendingApproval: null,
  pendingClarification: null,
  workflowNotifications: 0,
  workflowSteps: [],
  workflowStreamingContent: "",
  setActiveWorkflow: (id) => set({ activeWorkflowId: id }),
  setActiveWorkflowAgent: (agent) => set({ activeWorkflowAgent: agent }),
  setActiveWorkflowTab: (tab) => set({ activeWorkflowTab: tab }),
  setPendingApproval: (approval) => set({ pendingApproval: approval }),
  setPendingClarification: (clarification) => set({ pendingClarification: clarification }),
  setWorkflowNotifications: (count) => set({ workflowNotifications: count }),
  incrementWorkflowNotifications: () => set((s) => ({ workflowNotifications: s.workflowNotifications + 1 })),
  // Workflow progress actions
  resetWorkflowProgress: () => {
    console.debug("[store] resetWorkflowProgress");
    set({ workflowSteps: [], workflowStreamingContent: "", activeWorkflowAgent: null });
  },
  addWorkflowStep: (agent) => {
    console.debug("[store] addWorkflowStep:", agent);
    set((s) => ({
      workflowSteps: [
        ...s.workflowSteps.filter((st) => st.agent !== agent),
        { agent, status: "running", startedAt: Date.now() },
      ],
      activeWorkflowAgent: agent,
    }));
  },
  completeWorkflowStep: (agent, phase, toolCalls) => {
    console.debug("[store] completeWorkflowStep:", agent, phase, toolCalls);
    set((s) => ({
      workflowSteps: s.workflowSteps.map((st) =>
        st.agent === agent
          ? { ...st, status: "completed" as const, phase, toolCalls, completedAt: Date.now() }
          : st,
      ),
      activeWorkflowAgent: null,
    }));
  },
  failWorkflowStep: (agent) =>
    set((s) => ({
      workflowSteps: s.workflowSteps.map((st) =>
        st.agent === agent ? { ...st, status: "failed" as const, completedAt: Date.now() } : st,
      ),
      activeWorkflowAgent: null,
    })),
  appendWorkflowContent: (text) =>
    set((s) => ({ workflowStreamingContent: s.workflowStreamingContent + text })),
  setWorkflowStreamingContent: (content) => set({ workflowStreamingContent: content }),
}));
