import { useRef, useEffect, useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FlexBox,
  Button,
  ComboBox,
  ComboBoxItem,
  BusyIndicator,
  IllustratedMessage,
  MessageStrip,
  Input,
  Select,
  Option,
  Icon,
} from "@ui5/webcomponents-react";
import "@ui5/webcomponents-fiori/dist/illustrations/BeforeSearch.js";
import "@ui5/webcomponents-fiori/dist/illustrations/NoData.js";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../../../convex/_generated/api";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";
import { ApprovalPanel } from "../workflow/ApprovalPanel";
import { useAppStore } from "@/stores/appStore";
import { useChatMessages } from "@/hooks/useChat";
import { useLLMModels } from "@/hooks/useLLMModels";
import type { Id } from "../../../../../convex/_generated/dataModel";

export function ChatPanel() {
  const navigate = useNavigate();
  const {
    activeSystemId,
    activeSessionId,
    activeWorkflowId,
    setActiveSession,
    selectedModel,
    setSelectedModel,
    toggleContextPanel,
    contextPanelOpen,
    isStreaming,
  } = useAppStore();

  const { messages, sendMessage, stopStreaming, resumeChat, answerChat } = useChatMessages(activeSessionId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const models = useLLMModels();

  const system = useQuery(api.systems.get, activeSystemId ? { id: activeSystemId as Id<"systems"> } : "skip");
  const activeWorkflow = useQuery(api.workflows.get, activeWorkflowId ? { id: activeWorkflowId as Id<"workflows"> } : "skip");
  const createSession = useMutation(api.sessions.create);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSend = useCallback(async (content: string) => {
    if (!activeSystemId) return;
    let sessionId = activeSessionId;
    if (!sessionId) {
      const title = content.length > 50 ? content.slice(0, 47) + "..." : content;
      sessionId = await createSession({ systemId: activeSystemId as Id<"systems">, title });
      setActiveSession(sessionId);
    }
    sendMessage(content, sessionId ?? undefined);
  }, [activeSystemId, activeSessionId, createSession, setActiveSession, sendMessage]);

  return (
    <div className="chat-workspace">
      <div className="chat-workspace__hero">
        <div>
          <div className="chat-workspace__eyebrow">SAP-native conversation</div>
          <h1 className="chat-workspace__title">{activeSessionId ? "Conversation" : "New Conversation"}</h1>
          <p className="chat-workspace__subtitle">
            Ask about SAP objects, start workflows, inspect tool activity, and steer approvals without leaving the workspace.
          </p>
        </div>
        <div className="chat-workspace__hero-actions">
          <div className="chat-chip-stack">
            {system ? (
              <span className="chat-context-chip">{system.name} • Client {system.client}</span>
            ) : (
              <span className="chat-context-chip">No SAP system selected</span>
            )}
            <span className="chat-context-chip">{activeSessionId ? "Live session" : "Draft session"}</span>
          </div>
          <FlexBox alignItems="Center" style={{ gap: 8 }}>
            <ComboBox className="chat-model-select" value={models.find((m) => m.id === selectedModel)?.name ?? ""}
              onSelectionChange={(e) => {
                const val = (e.detail as { item?: { getAttribute: (k: string) => string } }).item?.getAttribute("data-id");
                if (val) setSelectedModel(val);
              }}
            >
              {models.map((m) => <ComboBoxItem key={m.id} data-id={m.id} text={m.name} />)}
            </ComboBox>
            <Button icon={contextPanelOpen ? "exit-full-screen" : "full-screen"} design="Transparent" tooltip="Toggle context panel" onClick={toggleContextPanel} />
          </FlexBox>
        </div>
      </div>

      {/* Active workflow banner */}
      {activeWorkflow && (
        <MessageStrip design="Information" hideCloseButton
          style={{ borderRadius: 16, cursor: "pointer", margin: "0 var(--space-xl)" }}
          onClick={() => navigate(`/workflows/${activeWorkflow._id}`)}
        >
          Active workflow: <strong>{activeWorkflow.type?.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}</strong>
          &nbsp;&mdash; Phase: <strong>{activeWorkflow.phase}</strong>
          &nbsp;&middot; Click to view details
        </MessageStrip>
      )}

      {/* Messages area */}
      <div className="chat-workspace__body">
        <div className="chat-surface">
          <div className="chat-surface__header">
            <div>
              <div className="chat-surface__label">Conversation stream</div>
              <div className="chat-surface__meta">
                {messages.length} message{messages.length === 1 ? "" : "s"}
                {activeWorkflow ? " • workflow attached" : " • chat only"}
              </div>
            </div>
            {isStreaming && (
              <div className="chat-stream-indicator">
                <BusyIndicator active size="S" />
                <span>SAP Copilot is working…</span>
              </div>
            )}
          </div>

          <div className="sap-scroll chat-messages chat-surface__messages">
            {messages.length === 0 && !activeSessionId ? (
              <WelcomeScreen onSend={handleSend} />
            ) : messages.length === 0 ? (
              <div className="chat-empty-panel">
                <IllustratedMessage name="NoData" titleText="No messages yet" subtitleText="Start the conversation below" />
              </div>
            ) : (
              <MessageList messages={messages} />
            )}
            <InlineApprovalCard resumeChat={resumeChat} />
            <InlineClarificationCard answerChat={answerChat} />
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} onStop={stopStreaming} disabled={!activeSystemId} isStreaming={isStreaming} />
    </div>
  );
}

function WelcomeScreen({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="chat-welcome">
      <div className="chat-welcome__intro">
        <IllustratedMessage name="BeforeSearch" titleText="Welcome to SAP Copilot" subtitleText="Connect to an SAP system and start a conversation. Ask me to read code, search objects, run tests, manage transports, and more." />
      </div>
      <div className="chat-welcome__prompts">
        {STARTER_PROMPTS.map((p) => (
          <button key={p.text} onClick={() => onSend(p.text)} className="chat-starter-card">
            <div className="chat-starter-card__label-row">
              <Icon name={p.icon} style={{ fontSize: 13, color: "var(--color-accent)" }} />
              <span className="chat-starter-card__label">{p.category}</span>
            </div>
            <div className="chat-starter-card__text">{p.text}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

const STARTER_PROMPTS = [
  { icon: "source-code", category: "Read", text: "Show me the source of Z_MY_REPORT" },
  { icon: "search", category: "Search", text: "Find all classes in package ZDEV" },
  { icon: "lab", category: "Test", text: "Run unit tests for ZCL_CALCULATOR" },
  { icon: "shipping-status", category: "Transport", text: "List my open transport requests" },
];

function InlineApprovalCard({ resumeChat }: { resumeChat: (workflowId: string, approved: boolean, feedback: string) => void }) {
  const { pendingApproval, setPendingApproval } = useAppStore();
  if (!pendingApproval) return null;
  return (
    <div className="chat-inline-panel">
      <div className="chat-inline-panel__label">SAP Copilot</div>
      <ApprovalPanel
        approval={pendingApproval}
        onApprove={() => { resumeChat(pendingApproval.workflow_id, true, ""); setPendingApproval(null); }}
        onReject={(feedback) => { resumeChat(pendingApproval.workflow_id, false, feedback); setPendingApproval(null); }}
      />
    </div>
  );
}

function InlineClarificationCard({ answerChat }: { answerChat: (workflowId: string, answers: Array<{ id: string; answer: string }>) => void }) {
  const { pendingClarification, setPendingClarification } = useAppStore();
  if (!pendingClarification) return null;
  return (
    <div className="chat-inline-panel">
      <div className="chat-inline-panel__label">SAP Copilot</div>
      <div className="sap-card" style={{ border: "2px solid var(--sapInformationBorderColor)" }}>
        <div className="sap-card__header" style={{ borderBottom: "1px solid var(--sapInformationBorderColor)", background: "var(--sapInformationBackground)" }}>
          <Icon name="question-mark" style={{ fontSize: 16, color: "var(--sapInformationColor)" }} />
          <span style={{ fontWeight: 600, fontSize: "var(--font-size-base)", color: "var(--sapTextColor)" }}>Clarification Needed</span>
        </div>
        <div className="sap-card__body">
          <ClarificationForm
            questions={pendingClarification.questions}
            onSubmit={(answers) => { answerChat(pendingClarification.workflow_id, answers); setPendingClarification(null); }}
          />
        </div>
      </div>
    </div>
  );
}

type ClarQuestion = { id: string; question: string; type: string; options?: string[]; required: boolean; default?: string };

function ClarificationForm({ questions, onSubmit }: { questions: ClarQuestion[]; onSubmit: (a: { id: string; answer: string }[]) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const set = (id: string, v: string) => setAnswers((p) => ({ ...p, [id]: v }));
  const allDone = questions.filter((q) => q.required).every((q) => (answers[q.id] || "").trim());

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>Please answer the following to continue:</p>
      {questions.map((q, i) => (
        <div key={q.id} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--color-text-primary)" }}>
            {i + 1}. {q.question}{q.required && <span style={{ color: "var(--sapNegativeColor)" }}> *</span>}
          </label>
          {q.type === "select" && q.options ? (
            <Select onChange={(e: CustomEvent<{ selectedOption?: Element }>) => set(q.id, (e.detail?.selectedOption as HTMLElement | undefined)?.textContent?.trim() ?? "")}>
              <Option value="">Select&hellip;</Option>
              {q.options.map((o) => <Option key={o} value={o} selected={answers[q.id] === o}>{o}</Option>)}
            </Select>
          ) : q.type === "confirm" ? (
            <FlexBox style={{ gap: 8 }}>
              {["yes", "no"].map((val) => (
                <Button key={val} design={answers[q.id] === val ? (val === "yes" ? "Positive" : "Negative") : "Default"} onClick={() => set(q.id, val)}>
                  {val === "yes" ? "Yes" : "No"}
                </Button>
              ))}
            </FlexBox>
          ) : (
            <Input value={answers[q.id] || ""} placeholder={q.default || "Type your answer…"} onInput={(e: Event) => set(q.id, ((e.target as HTMLInputElement) || { value: "" }).value)} />
          )}
        </div>
      ))}
      <Button design="Emphasized" disabled={!allDone} onClick={() => onSubmit(questions.map((q) => ({ id: q.id, answer: answers[q.id] || q.default || "" })))}>
        Submit Answers
      </Button>
    </div>
  );
}
