import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  FlexBox,
  Tag,
  Dialog,
  Bar,
  Icon,
  ObjectStatus,
} from "@ui5/webcomponents-react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../../../convex/_generated/api";
import { useAppStore } from "@/stores/appStore";
import { AddSystemDialog } from "../system/AddSystemDialog";
import type { SystemFormData } from "../system/AddSystemDialog";
import { EditSystemDialog } from "../system/EditSystemDialog";
import type { EditSystemData } from "../system/EditSystemDialog";
import { connectSystem, disconnectSystem, listConnectedSystems } from "@/lib/gateway";
import type { Id } from "../../../../../convex/_generated/dataModel";
import type { WorkflowApproval, WorkflowStep, Workflow } from "@sap-copilot/shared";

interface SidebarProps {
  onStartWorkflow?: (type: string) => void;
}

interface SapSystem {
  _id: string;
  name: string;
  client: string;
  color?: string;
  status: string;
  description?: string;
  baseUrl: string;
  language: string;
  username: string;
  password: string;
  proxy?: string;
  lastConnected?: number;
  lastError?: string;
}

interface SapSession {
  _id: string;
  title: string;
  systemId: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  toolCallCount: number;
}

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function phaseColor(phase: string): "Positive" | "Negative" | "Critical" | "Information" | "None" {
  if (phase === "completed") return "Positive";
  if (phase === "failed") return "Negative";
  if (phase === "paused") return "Critical";
  if (["planning", "clarifying", "coding", "reviewing", "testing", "activating", "analyzing"].includes(phase)) return "Information";
  return "None";
}

export function Sidebar({ onStartWorkflow: _onStartWorkflow }: SidebarProps) {
  const navigate = useNavigate();
  const { activeSystemId, activeSessionId, activeWorkflowId, setActiveSystem, setActiveSession, setActiveWorkflow } = useAppStore();

  const [showAddSystem, setShowAddSystem] = useState(false);
  const [editSystem, setEditSystem] = useState<EditSystemData | null>(null);
  const [deleteSessionId, setDeleteSessionId] = useState<string | null>(null);
  const [systemsOpen, setSystemsOpen] = useState(true);
  const [chatsOpen, setChatsOpen] = useState(true);
  const [workflowsOpen, setWorkflowsOpen] = useState(true);

  const systems = (useQuery(api.systems.list) ?? []) as SapSystem[];
  const sessions = (useQuery(api.sessions.listBySystem, activeSystemId ? { systemId: activeSystemId as Id<"systems"> } : "skip") ?? []) as SapSession[];
  const rawWorkflows = (useQuery(api.workflows.listBySystem, activeSystemId ? { systemId: activeSystemId as Id<"systems"> } : "skip") ?? []) as any[];
  const workflows: Workflow[] = rawWorkflows.map((wf) => ({
    id: wf._id, sessionId: wf.sessionId, systemId: wf.systemId, type: wf.type,
    status: wf.status, phase: wf.phase, userRequest: wf.userRequest, plan: wf.plan,
    artifacts: wf.artifacts, metadata: wf.metadata,
    approvals: (wf.approvals ?? []) as WorkflowApproval[],
    steps: (wf.steps ?? []) as WorkflowStep[],
    error: wf.error, createdAt: wf.createdAt, updatedAt: wf.updatedAt,
  }));

  const addSystemMutation = useMutation(api.systems.add);
  const updateSystemMutation = useMutation(api.systems.update);
  const createSession = useMutation(api.sessions.create);
  const removeSession = useMutation(api.sessions.remove);
  const updateStatus = useMutation(api.systems.updateStatus);

  const reconnectingRef = useRef(false);
  useEffect(() => {
    if (!activeSystemId || reconnectingRef.current) return;
    const sys = systems.find((s) => s._id === activeSystemId);
    if (!sys) return;
    let cancelled = false;
    (async () => {
      try {
        const { connected } = await listConnectedSystems();
        if (cancelled || connected.includes(activeSystemId)) return;
        reconnectingRef.current = true;
        await updateStatus({ id: activeSystemId as Id<"systems">, status: "connecting" });
        await connectSystem({ system_id: activeSystemId, url: sys.baseUrl, user: sys.username, password: sys.password, client: sys.client, language: sys.language, proxy: sys.proxy });
        if (!cancelled) await updateStatus({ id: activeSystemId as Id<"systems">, status: "connected", lastConnected: Date.now() });
      } catch (e) {
        if (!cancelled) await updateStatus({ id: activeSystemId as Id<"systems">, status: "error", lastError: (e as Error).message }).catch(() => {});
      } finally { reconnectingRef.current = false; }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSystemId, systems.length]);

  const handleAddSystem = async (data: SystemFormData) => {
    const id = await addSystemMutation({ name: data.name, description: data.description || undefined, baseUrl: data.url, client: data.client, language: data.language, username: data.user, password: data.password, proxy: data.proxy || undefined, color: data.color });
    setActiveSystem(id);
  };

  const handleSaveSystem = async (data: EditSystemData) => {
    await updateSystemMutation({ id: data.id as Id<"systems">, name: data.name, description: data.description, baseUrl: data.baseUrl, client: data.client, language: data.language, username: data.username, password: data.password, proxy: data.proxy, color: data.color });
    try { await disconnectSystem(data.id); } catch { /* may not be connected */ }
    try {
      await updateStatus({ id: data.id as Id<"systems">, status: "connecting" });
      await connectSystem({ system_id: data.id, url: data.baseUrl, user: data.username, password: data.password, client: data.client, language: data.language, proxy: data.proxy });
      await updateStatus({ id: data.id as Id<"systems">, status: "connected", lastConnected: Date.now() });
    } catch (e) {
      await updateStatus({ id: data.id as Id<"systems">, status: "error", lastError: (e as Error).message });
    }
  };

  const handleSelectSystem = async (sys: (typeof systems)[number]) => {
    setActiveSystem(sys._id);
    let needsConnect = sys.status !== "connected";
    if (!needsConnect) {
      try { const { connected } = await listConnectedSystems(); needsConnect = !connected.includes(sys._id); }
      catch { needsConnect = true; }
    }
    if (needsConnect) {
      try {
        await updateStatus({ id: sys._id as Id<"systems">, status: "connecting" });
        await connectSystem({ system_id: sys._id, url: sys.baseUrl, user: sys.username, password: sys.password, client: sys.client, language: sys.language, proxy: sys.proxy });
        await updateStatus({ id: sys._id as Id<"systems">, status: "connected", lastConnected: Date.now() });
      } catch (e) {
        await updateStatus({ id: sys._id as Id<"systems">, status: "error", lastError: (e as Error).message });
      }
    }
  };

  const handleEditSystem = (sys: (typeof systems)[number], e: React.MouseEvent) => {
    e.stopPropagation();
    setEditSystem({ id: sys._id, name: sys.name, description: sys.description, baseUrl: sys.baseUrl, client: sys.client, language: sys.language, username: sys.username, password: sys.password, proxy: sys.proxy, color: sys.color ?? "#0070f2" });
  };

  const handleNewChat = async () => {
    if (!activeSystemId) return;
    const sid = await createSession({ systemId: activeSystemId as Id<"systems"> });
    setActiveSession(sid);
    navigate("/");
  };

  const handleDeleteChat = async () => {
    if (!deleteSessionId) return;
    if (activeSessionId === deleteSessionId) setActiveSession(null);
    await removeSession({ id: deleteSessionId as Id<"sessions"> });
    setDeleteSessionId(null);
  };

  const pendingWorkflows = workflows.filter((w) => w.approvals.some((a) => a.status === "pending")).length;
  const activeSystem = systems.find((system) => system._id === activeSystemId) ?? null;

  return (
    <div className="sap-scroll app-sidebar-shell">
      <div className="app-sidebar-tenant-card">
        <div className="app-sidebar-tenant-card__eyebrow">Workspace</div>
        <div className="app-sidebar-tenant-card__title">{activeSystem?.name ?? "SAP Copilot"}</div>
        <div className="app-sidebar-tenant-card__subtitle">{activeSystem ? `Client ${activeSystem.client}` : "Connect a tenant to begin"}</div>
        <div className="app-sidebar-tenant-card__meta">
          {pendingWorkflows === 0 ? "No approvals pending" : `${pendingWorkflows} approval${pendingWorkflows === 1 ? "" : "s"} pending`}
        </div>
      </div>

      {/* SYSTEMS */}
      <SectionHeader title="SAP Systems" icon="system-exit" open={systemsOpen} onToggle={() => setSystemsOpen((o) => !o)}
        action={<Button icon="add" design="Transparent" tooltip="Add SAP System" accessibleName="Add System" onClick={() => setShowAddSystem(true)} />}
      />
      {systemsOpen && (
        <div className="app-sidebar-list">
          {systems.length === 0 && <EmptyHint icon="private-connected-to-landscape" text="No systems. Click + to add one." />}
          {systems.map((sys) => {
            const isActive = activeSystemId === sys._id;
            return (
              <div key={sys._id} role="button" tabIndex={0}
                onClick={() => handleSelectSystem(sys)}
                onKeyDown={(e) => e.key === "Enter" && handleSelectSystem(sys)}
                className={`app-sidebar-item ${isActive ? "app-sidebar-item--active" : ""}`}
                style={{ borderLeftColor: sys.color ?? "var(--color-accent)" }}
                onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "var(--sapList_Hover_Background)"; }}
                onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <span className={`status-dot ${sys.status}`} />
                <div className="app-sidebar-item__body">
                  <div className="app-sidebar-item__title">{sys.name}</div>
                  <div className="app-sidebar-item__subtitle">Client {sys.client}</div>
                </div>
                <Button icon="edit" design="Transparent" tooltip="Edit System" accessibleName={`Edit ${sys.name}`}
                  onClick={(e) => handleEditSystem(sys, e as unknown as React.MouseEvent)}
                  style={{ minWidth: 0, padding: 0, flexShrink: 0 }} />
              </div>
            );
          })}
        </div>
      )}

      <div className="sap-section-divider" />

      {/* CONVERSATIONS */}
      <SectionHeader title="Conversations" icon="discussion" open={chatsOpen} onToggle={() => setChatsOpen((o) => !o)}
        action={<Button icon="add" design="Transparent" tooltip="New Conversation" accessibleName="New Chat" disabled={!activeSystemId} onClick={handleNewChat} />}
      />
      {chatsOpen && (
        <div className="sap-scroll app-sidebar-list app-sidebar-list--scroll">
          {!activeSystemId && <EmptyHint icon="chain-link-off" text="Select a system to see conversations." />}
          {activeSystemId && sessions.length === 0 && <EmptyHint icon="discussion" text="No conversations yet. Click + to start." />}
          {sessions.map((session) => {
            const isActive = activeSessionId === session._id;
            return (
              <div key={session._id} role="button" tabIndex={0}
                onClick={() => { setActiveSession(session._id); navigate("/"); }}
                onKeyDown={(e) => { if (e.key === "Enter") { setActiveSession(session._id); navigate("/"); } }}
                className={`app-sidebar-item ${isActive ? "app-sidebar-item--active" : ""}`}
                onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "var(--sapList_Hover_Background)"; }}
                onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <Icon name="discussion" style={{ fontSize: 14, color: "var(--color-text-secondary)", flexShrink: 0, marginRight: 8 }} />
                <div className="app-sidebar-item__body">
                  <div className="app-sidebar-item__title">{session.title}</div>
                  <div className="app-sidebar-item__subtitle">{formatRelativeTime(session.updatedAt)}</div>
                </div>
                <Button icon="delete" design="Transparent" tooltip="Delete Conversation" accessibleName={`Delete ${session.title}`}
                  onClick={(e) => { e.stopPropagation(); setDeleteSessionId(session._id); }}
                  style={{ minWidth: 0, padding: 0, flexShrink: 0 }} />
              </div>
            );
          })}
        </div>
      )}

      {/* WORKFLOWS */}
      {activeSystemId && (
        <>
          <div className="sap-section-divider" />
          <SectionHeader title="Workflows" icon="workflow-tasks" open={workflowsOpen} onToggle={() => setWorkflowsOpen((o) => !o)}
            badge={pendingWorkflows > 0 ? String(pendingWorkflows) : undefined}
            action={<Button icon="add" design="Transparent" tooltip="Browse Workflow Catalog" accessibleName="New Workflow" onClick={() => navigate("/workflows")} />}
          />
          {workflowsOpen && (
            <div className="sap-scroll app-sidebar-list app-sidebar-list--workflow">
              {workflows.length === 0 && <EmptyHint icon="workflow-tasks" text="No workflows yet." />}
              {workflows.map((wf) => {
                const isActive = activeWorkflowId === wf.id;
                const hasPending = wf.approvals.some((a) => a.status === "pending");
                return (
                  <div key={wf.id} role="button" tabIndex={0}
                    onClick={() => { setActiveWorkflow(wf.id); navigate(`/workflows/${wf.id}`); }}
                    onKeyDown={(e) => { if (e.key === "Enter") { setActiveWorkflow(wf.id); navigate(`/workflows/${wf.id}`); } }}
                    className={`app-sidebar-item app-sidebar-item--workflow ${isActive ? "app-sidebar-item--active" : ""}`}
                    onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "var(--sapList_Hover_Background)"; }}
                    onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <Icon name="workflow-tasks" style={{ fontSize: 13, color: "var(--color-text-secondary)", flexShrink: 0, marginTop: 2 }} />
                    <div className="app-sidebar-item__body">
                      <div className="app-sidebar-item__title app-sidebar-item__title--workflow">
                        {wf.type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      </div>
                      <div className="app-sidebar-item__subtitle app-sidebar-item__subtitle--wrap">{wf.userRequest}</div>
                      <div className="app-sidebar-item__badges">
                        <ObjectStatus state={phaseColor(wf.phase)} style={{ fontSize: "10px" }}>{wf.phase}</ObjectStatus>
                        {hasPending && <Tag colorScheme="6" style={{ fontSize: "10px" }}>Approval</Tag>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      <div style={{ flex: 1 }} />

      <Dialog open={deleteSessionId !== null} headerText="Delete Conversation" onClose={() => setDeleteSessionId(null)}
        footer={<Bar endContent={<FlexBox style={{ gap: 8 }}><Button design="Transparent" onClick={() => setDeleteSessionId(null)}>Cancel</Button><Button design="Negative" onClick={handleDeleteChat}>Delete</Button></FlexBox>} />}
      >
        <div style={{ padding: "var(--space-lg)" }}>
          <p style={{ fontSize: "var(--font-size-base)", color: "var(--color-text-primary)", marginBottom: 8 }}>Delete this conversation?</p>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>All messages will be permanently removed.</p>
        </div>
      </Dialog>

      <AddSystemDialog open={showAddSystem} onClose={() => setShowAddSystem(false)} onAdd={handleAddSystem} />
      <EditSystemDialog open={editSystem !== null} system={editSystem} onClose={() => setEditSystem(null)} onSave={handleSaveSystem} />
    </div>
  );
}

function SectionHeader({ title, icon, open, onToggle, action, badge }: { title: string; icon: string; open: boolean; onToggle: () => void; action?: React.ReactNode; badge?: string; }) {
  return (
    <div className="app-sidebar-section-header">
      <button onClick={onToggle} aria-expanded={open}
        className="app-sidebar-section-header__toggle"
      >
        <Icon name={icon} style={{ fontSize: 13, color: "var(--color-text-secondary)" }} />
        <span className="app-sidebar-section-header__title">{title}</span>
        {badge && <Tag colorScheme="6" style={{ fontSize: "10px", marginLeft: 2 }}>{badge}</Tag>}
        <Icon name={open ? "navigation-down-arrow" : "navigation-right-arrow"} style={{ fontSize: 10, marginLeft: "auto", color: "var(--color-text-secondary)" }} />
      </button>
      {action}
    </div>
  );
}

function EmptyHint({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="app-sidebar-empty-hint">
      <Icon name={icon} style={{ fontSize: 13, opacity: 0.5 }} />
      {text}
    </div>
  );
}
