import { useState, useCallback } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import {
  ShellBar,
  ShellBarItem,
  Button,
  Toast,
  Popover,
  List,
  ListItemStandard,
} from "@ui5/webcomponents-react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../../../convex/_generated/api";
import { Sidebar } from "./Sidebar";
import { ChatPanel } from "../chat/ChatPanel";
import { ContextPanel } from "../context/ContextPanel";
import { LLMConfigDialog } from "../settings/LLMConfigDialog";
import { WorkflowWorkspacePage } from "../workflow/WorkflowWorkspacePage";
import { StartWorkflowDialog } from "../workflow/StartWorkflowDialog";
import { useAppStore } from "@/stores/appStore";
import { startWorkflow } from "@/lib/gateway";
import { setTheme } from "@ui5/webcomponents-base/dist/config/Theme.js";
import type { Id } from "../../../../../convex/_generated/dataModel";

const THEMES = [
  { id: "sap_horizon",               label: "Horizon Light" },
  { id: "sap_horizon_dark",          label: "Horizon Dark" },
  { id: "sap_horizon_hcb",           label: "High Contrast Black" },
];

export function ShellLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const {
    sidebarCollapsed,
    toggleSidebar,
    activeSystemId,
    activeSessionId,
    setActiveSession,
    activeWorkflowId,
    contextPanelOpen,
    setActiveWorkflowAgent,
    incrementWorkflowNotifications,
    setPendingApproval,
    setPendingClarification,
  } = useAppStore();

  const [llmDialogOpen, setLlmDialogOpen]   = useState(false);
  const [startDialogType, setStartDialogType] = useState<string | null>(null);
  const [toastMessage, setToastMessage]       = useState("");
  const [toastOpen, setToastOpen]             = useState(false);
  const [themeMenuOpen, setThemeMenuOpen]     = useState(false);
  const [currentTheme, setCurrentTheme]       = useState(
    () => localStorage.getItem("sap_copilot_theme") ?? "sap_horizon"
  );

  const createSession = useMutation(api.sessions.create);
  const isWorkflowRoute = location.pathname.startsWith("/workflows");

  const pendingCount = useQuery(
    api.workflows.countPendingApprovals,
    activeSystemId ? { systemId: activeSystemId as Id<"systems"> } : "skip",
  );

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setToastOpen(true);
  }, []);

  const handleThemeChange = (themeId: string) => {
    setTheme(themeId);
    setCurrentTheme(themeId);
    localStorage.setItem("sap_copilot_theme", themeId);
    setThemeMenuOpen(false);
  };

  const handleStartWorkflow = (type: string, request: string) => {
    if (!activeSystemId || !activeSessionId) return;

    startWorkflow(
      { system_id: activeSystemId, session_id: activeSessionId, workflow_type: type, user_request: request },
      {
        onWorkflowStart: () => { showToast("Workflow started"); },
        onAgentStart: (data) => { setActiveWorkflowAgent(data.agent); },
        onAgentEnd: () => { setActiveWorkflowAgent(null); },
        onContent: () => {},
        onToolStart: () => {},
        onToolEnd: () => {},
        onApprovalRequired: (data) => {
          setPendingApproval({
            workflow_id: data.workflow_id,
            id: "",
            phase: "",
            details: JSON.stringify(data.data),
            status: "pending",
            requestedAt: Date.now(),
          });
          incrementWorkflowNotifications();
          showToast("Approval required â€” review before continuing");
        },
        onClarificationRequired: (data) => {
          setPendingClarification({
            workflow_id: data.workflow_id,
            questions: data.questions.map((q) => ({
              id: q.id,
              question: q.question,
              type: (q.question_type || "text") as "text" | "select" | "confirm",
              options: q.options,
              required: q.required,
            })),
          });
          incrementWorkflowNotifications();
        },
        onWorkflowPaused:   () => {},
        onWorkflowResumed:  () => {},
        onWorkflowComplete: () => { showToast("Workflow completed successfully"); },
        onError: (data) => { showToast(`Workflow error: ${data.message}`); },
      },
    );
  };

  const themeLabel = THEMES.find((t) => t.id === currentTheme)?.label ?? "Theme";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>

      {/* â”€â”€â”€ SAP Fiori ShellBar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <ShellBar
        primaryTitle="SAP ADT App"
        secondaryTitle="LangGraph orchestration for SAP-native AI delivery"
        logo={
          <img
            src="/sap-logo.svg"
            alt="SAP"
            style={{ height: 26, marginRight: 8 }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        }
        startButton={
          <Button
            icon={sidebarCollapsed ? "menu2" : "menu"}
            design="Transparent"
            onClick={toggleSidebar}
            tooltip={sidebarCollapsed ? "Expand Navigation" : "Collapse Navigation"}
            accessibleName="Toggle Navigation"
          />
        }
        profile={
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              background: "var(--sapAccentColor6)",
              color: "var(--sapContent_ContrastTextColor)",
              fontSize: 12,
              fontWeight: 700,
            }}
            aria-label="User Profile"
          >
            RV
          </div>
        }
        notificationsCount={String(pendingCount ?? 0)}
        style={{ position: "sticky", top: 0, zIndex: 100, flexShrink: 0 }}
      >
        {/* Workflow Catalog */}
        <ShellBarItem
          icon="workflow-tasks"
          text="Workflows"
          onClick={() => {
            if (location.pathname === "/workflows") {
              navigate("/");
            } else {
              navigate("/workflows");
            }
          }}
        />

        {/* Pending approvals bell */}
        {(pendingCount ?? 0) > 0 && (
          <ShellBarItem
            icon="bell"
            text={`${pendingCount} Pending`}
            onClick={() => {
              if (activeWorkflowId) navigate(`/workflows/${activeWorkflowId}`);
            }}
          />
        )}

        {/* Theme switcher */}
        <ShellBarItem
          id="theme-menu-trigger"
          icon="palette"
          text={themeLabel}
          onClick={() => setThemeMenuOpen(true)}
        />

        {/* LLM Settings */}
        <ShellBarItem
          icon="action-settings"
          text="LLM Settings"
          onClick={() => setLlmDialogOpen(true)}
        />
      </ShellBar>

      {/* Theme switcher popover */}
      <Popover
        opener="theme-menu-trigger"
        open={themeMenuOpen}
        onClose={() => setThemeMenuOpen(false)}
        placement="Bottom"
        headerText="Select Theme"
      >
        <List onItemClick={(e) => handleThemeChange((e.detail.item as HTMLElement).dataset.theme ?? "sap_horizon")}>
          {THEMES.map((t) => (
            <ListItemStandard
              key={t.id}
              data-theme={t.id}
              selected={currentTheme === t.id}
              icon={currentTheme === t.id ? "accept" : ""}
            >
              {t.label}
            </ListItemStandard>
          ))}
        </List>
      </Popover>

      <LLMConfigDialog open={llmDialogOpen} onClose={() => setLlmDialogOpen(false)} />

      {/* â”€â”€â”€ Body: Sidebar + Content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* Left Navigation Sidebar */}
        <div
          className="sap-sidebar-transition"
          style={{
            width: sidebarCollapsed ? 0 : "var(--sidebar-width)",
            overflow: "hidden",
            flexShrink: 0,
            borderRight: sidebarCollapsed ? "none" : "1px solid var(--color-border-default)",
            background: "var(--color-bg-list)",
          }}
        >
          {!sidebarCollapsed && (
            <Sidebar
              onStartWorkflow={(type) => {
                setStartDialogType(type);
                navigate("/workflows");
              }}
            />
          )}
        </div>

        {/* â”€â”€â”€ Main Content Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", minWidth: 0 }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
            <Routes>
              {/* Chat (default) */}
              <Route path="/" element={<ChatPanel />} />

              {/* Workflow Catalog */}
              <Route
                path="/workflows"
                element={
                  <WorkflowWorkspacePage
                    onStartWorkflow={async (type) => {
                      if (!activeSystemId) { showToast("Please connect to a SAP System first"); return; }
                      if (!activeSessionId) {
                        try {
                          const sid = await createSession({
                            systemId: activeSystemId as Id<"systems">,
                            title: `Workflow: ${type.replace(/_/g, " ")}`,
                          });
                          setActiveSession(sid);
                        } catch { showToast("Failed to create session"); return; }
                      }
                      setStartDialogType(type);
                    }}
                  />
                }
              />

              {/* Workflow Detail */}
              <Route
                path="/workflows/:id"
                element={
                  <WorkflowWorkspacePage
                    onStartWorkflow={async (type) => {
                      if (!activeSystemId) { showToast("Please connect to a SAP System first"); return; }
                      if (!activeSessionId) {
                        try {
                          const sid = await createSession({
                            systemId: activeSystemId as Id<"systems">,
                            title: `Workflow: ${type.replace(/_/g, " ")}`,
                          });
                          setActiveSession(sid);
                        } catch { showToast("Failed to create session"); return; }
                      }
                      setStartDialogType(type);
                    }}
                  />
                }
              />

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>

          {contextPanelOpen && !isWorkflowRoute && (
            <div
              style={{
                width: "min(34vw, 420px)",
                minWidth: 320,
                borderLeft: "1px solid var(--color-border-default)",
                background: "rgba(255, 255, 255, 0.82)",
                backdropFilter: "blur(12px)",
                overflow: "hidden",
                flexShrink: 0,
              }}
            >
              <ContextPanel />
            </div>
          )}
        </div>
      </div>

      {/* Start Workflow Dialog */}
      <StartWorkflowDialog
        workflowType={startDialogType ?? ""}
        open={startDialogType !== null}
        onClose={() => setStartDialogType(null)}
        onStart={(type, req) => {
          handleStartWorkflow(type, req);
          navigate("/");
        }}
      />

      {/* Toast notifications */}
      <Toast
        open={toastOpen}
        duration={4000}
        placement="BottomCenter"
        onClose={() => setToastOpen(false)}
      >
        {toastMessage}
      </Toast>
    </div>
  );
}
