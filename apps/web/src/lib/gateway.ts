import type { WorkflowGraphEdge, WorkflowGraphNode } from "@sap-copilot/shared";

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "";

// ─── Types ───

export interface ConnectRequest {
  system_id: string;
  url: string;
  user: string;
  password: string;
  client?: string;
  language?: string;
  insecure?: boolean;
  read_only?: boolean;
  proxy?: string;
}

export interface ConnectResponse {
  system_id: string;
  status: string;
  tools_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatStreamEvent {
  type: "content" | "tool_start" | "tool_end" | "error" | "done";
  data: Record<string, unknown>;
}

// ─── System Management ───

export async function connectSystem(req: ConnectRequest): Promise<ConnectResponse> {
  const res = await fetch(`${GATEWAY_URL}/api/systems/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to connect: ${detail}`);
  }
  return res.json();
}

export async function disconnectSystem(systemId: string): Promise<void> {
  await fetch(`${GATEWAY_URL}/api/systems/${encodeURIComponent(systemId)}/disconnect`, {
    method: "POST",
  });
}

export async function listConnectedSystems(): Promise<{ connected: string[] }> {
  const res = await fetch(`${GATEWAY_URL}/api/systems/`);
  return res.json();
}

export async function listTools(systemId: string): Promise<{ tools: unknown[] }> {
  const res = await fetch(`${GATEWAY_URL}/api/systems/${encodeURIComponent(systemId)}/tools`);
  if (!res.ok) throw new Error("Failed to list tools");
  return res.json();
}

// ─── Chat SSE Streaming ───

export function streamChat(
  systemId: string,
  messages: ChatMessage[],
  model: string,
  callbacks: {
    onContent: (text: string) => void;
    onToolStart: (data: { id: string; name: string; parameters: Record<string, unknown> }) => void;
    onToolEnd: (data: { id: string; name: string; status: string; result: string; duration: number }) => void;
    onError: (message: string) => void;
    onDone: (content: string) => void;
    // Workflow-specific callbacks (optional — fired when intent classifier
    // routes the request to the LangGraph workflow engine)
    onWorkflowStart?: (data: { workflow_id: string; type: string; user_request: string }) => void;
    onAgentStart?: (data: { workflow_id: string; agent: string }) => void;
    onAgentEnd?: (data: { workflow_id: string; agent: string; phase: string }) => void;
    onApprovalRequired?: (data: { workflow_id: string; data: Record<string, unknown> }) => void;
    onClarificationRequired?: (data: { workflow_id: string; questions: Array<{ id: string; question: string; question_type: string; options?: string[]; required: boolean }> }) => void;
    onStepComplete?: (data: { workflow_id: string; step_id: string; agent: string; action: string; status: string; result: string; tool_calls: number }) => void;
    onWorkflowPaused?: (data: { workflow_id: string; reason: string }) => void;
    onWorkflowComplete?: (data: { workflow_id: string }) => void;
  },
  sessionId?: string,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_id: systemId, session_id: sessionId ?? "", messages, model }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError(`Gateway error: ${detail}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let receivedDone = false;

      function dispatchSSEEvent(eventType: string, eventData: string) {
        if (!eventType || !eventData) return;
        try {
          const data = JSON.parse(eventData);
          switch (eventType) {
            case "content":
              callbacks.onContent(data.text ?? "");
              break;
            case "tool_start":
              callbacks.onToolStart(data);
              break;
            case "tool_end":
              callbacks.onToolEnd(data);
              break;
            case "error":
              callbacks.onError(data.message ?? "Unknown error");
              receivedDone = true;
              break;
            case "done":
              callbacks.onDone(data.content ?? "");
              receivedDone = true;
              break;
            // Workflow events (when intent classifier routes to LangGraph)
            case "workflow_start":
              callbacks.onWorkflowStart?.(data);
              break;
            case "agent_start":
              callbacks.onAgentStart?.(data);
              break;
            case "agent_end":
              callbacks.onAgentEnd?.(data);
              break;
            case "approval_required":
              callbacks.onApprovalRequired?.(data);
              break;
            case "clarification_required":
              callbacks.onClarificationRequired?.(data);
              break;
            case "step_complete":
              callbacks.onStepComplete?.(data);
              break;
            case "workflow_paused":
              callbacks.onWorkflowPaused?.(data);
              receivedDone = true; // Prevent double-finalize when SSE stream closes
              break;
            case "workflow_complete":
              callbacks.onWorkflowComplete?.(data);
              callbacks.onDone("");
              receivedDone = true;
              break;
          }
        } catch {
          // Ignore malformed JSON
        }
      }

      let currentEventType = "";
      let currentEventData = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer (\r\n line endings from sse_starlette)
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // If we had a pending event, dispatch it (handles missing blank line)
            if (currentEventType && currentEventData) {
              dispatchSSEEvent(currentEventType, currentEventData);
            }
            currentEventType = line.slice(7).trim();
            currentEventData = "";
          } else if (line.startsWith("data: ")) {
            currentEventData = line.slice(6);
          } else if (line === "") {
            // Blank line = end of event
            if (currentEventType && currentEventData) {
              dispatchSSEEvent(currentEventType, currentEventData);
            }
            currentEventType = "";
            currentEventData = "";
          }
        }
      }

      // Flush any remaining buffered event (stream closed without trailing blank line)
      if (currentEventType && currentEventData) {
        dispatchSSEEvent(currentEventType, currentEventData);
      }
      // Also try to parse anything left in the buffer
      if (buffer.trim()) {
        const remainingLines = buffer.split(/\r?\n/);
        for (const line of remainingLines) {
          if (line.startsWith("event: ")) {
            if (currentEventType && currentEventData) {
              dispatchSSEEvent(currentEventType, currentEventData);
            }
            currentEventType = line.slice(7).trim();
            currentEventData = "";
          } else if (line.startsWith("data: ")) {
            currentEventData = line.slice(6);
          }
        }
        if (currentEventType && currentEventData) {
          dispatchSSEEvent(currentEventType, currentEventData);
        }
      }

      // If stream ended without a done/error event, call onDone as fallback
      // so the UI finalizes properly instead of showing "Connection Closed"
      if (!receivedDone) {
        callbacks.onDone("");
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError(`Stream error: ${(e as Error).message}`);
      }
    }
  })();

  return controller;
}

// ─── Health Check ───

export async function checkHealth(): Promise<{ status: string; connected_systems: string[] }> {
  const res = await fetch(`${GATEWAY_URL}/health`);
  return res.json();
}

// ─── System Test ───

export interface TestResult {
  status: "success" | "error";
  tools_count?: number;
  detail?: string;
}

export async function testSystemConnection(req: ConnectRequest): Promise<TestResult> {
  const res = await fetch(`${GATEWAY_URL}/api/systems/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const detail = await res.text();
    return { status: "error", detail: `Gateway error: ${detail}` };
  }
  return res.json();
}

// ─── LiteLLM Proxy Configuration ───

export interface LiteLLMConfig {
  base_url: string;
  api_key: string;
}

export interface LLMModel {
  id: string;
  name: string;
  owned_by: string;
}

export async function configureLiteLLM(config: LiteLLMConfig): Promise<void> {
  const res = await fetch(`${GATEWAY_URL}/api/llm/configure`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to configure LiteLLM: ${detail}`);
  }
}

export async function getLiteLLMConfig(): Promise<{ base_url: string; api_key_masked: string }> {
  const res = await fetch(`${GATEWAY_URL}/api/llm/config`);
  if (!res.ok) return { base_url: "", api_key_masked: "" };
  return res.json();
}

export async function listLLMModels(): Promise<LLMModel[]> {
  const res = await fetch(`${GATEWAY_URL}/api/llm/models`);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const data = await res.json();
  return data.models ?? [];
}

// ─── Workflow API ───

export interface StartWorkflowRequest {
  system_id: string;
  session_id: string;
  workflow_type: string;
  user_request: string;
}

export interface WorkflowStreamCallbacks {
  onWorkflowStart: (data: { workflow_id: string; type: string; user_request: string }) => void;
  onAgentStart: (data: { workflow_id: string; agent: string }) => void;
  onAgentEnd: (data: { workflow_id: string; agent: string; phase: string; step?: Record<string, unknown> }) => void;
  onContent: (data: { workflow_id: string; text: string; agent: string }) => void;
  onToolStart: (data: { workflow_id: string; name: string; input: string }) => void;
  onToolEnd: (data: { workflow_id: string; name: string; output: string }) => void;
  onStepComplete?: (data: { workflow_id: string; step_id: string; agent: string; action: string; status: string; result: string; tool_calls: number }) => void;
  onApprovalRequired: (data: { workflow_id: string; data: Record<string, unknown> }) => void;
  onClarificationRequired?: (data: { workflow_id: string; questions: Array<{ id: string; question: string; question_type: string; options?: string[]; required: boolean }> }) => void;
  onWorkflowPaused: (data: { workflow_id: string; reason: string }) => void;
  onWorkflowResumed: (data: { workflow_id: string; approved?: boolean; answers_count?: number }) => void;
  onStepSkipped?: (data: { workflow_id: string; step_id: string; reason: string }) => void;
  onWorkflowComplete: (data: { workflow_id: string }) => void;
  onError: (data: { workflow_id?: string; message: string }) => void;
}

function _parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: WorkflowStreamCallbacks,
): void {
  const decoder = new TextDecoder();
  let buffer = "";
  // Persist state across read chunks (critical!)
  let currentEventType = "";
  let currentEventData = "";

  (async () => {
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // If we had a pending event, dispatch it (handles missing blank line)
            if (currentEventType && currentEventData) {
              _dispatchWorkflowEvent(currentEventType, currentEventData, callbacks);
            }
            currentEventType = line.slice(7).trim();
            currentEventData = "";
          } else if (line.startsWith("data: ")) {
            currentEventData = line.slice(6);
          } else if (line === "") {
            if (currentEventType && currentEventData) {
              _dispatchWorkflowEvent(currentEventType, currentEventData, callbacks);
            }
            currentEventType = "";
            currentEventData = "";
          }
        }
      }
      // Flush remaining buffered event
      if (currentEventType && currentEventData) {
        _dispatchWorkflowEvent(currentEventType, currentEventData, callbacks);
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Stream error: ${(e as Error).message}` });
      }
    }
  })();
}

function _dispatchWorkflowEvent(
  eventType: string,
  eventData: string,
  callbacks: WorkflowStreamCallbacks,
): void {
  let data: unknown;
  try {
    data = JSON.parse(eventData);
  } catch {
    // Ignore malformed JSON
    return;
  }
  const handlerName = `on${eventType.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase()).replace(/^./, (c: string) => c.toUpperCase())}` as keyof WorkflowStreamCallbacks;
  const handler = callbacks[handlerName];
  console.debug(`[workflow-sse] ${eventType} → ${handlerName}`, handler ? "(handled)" : "(no handler)", data);
  if (typeof handler === "function") {
    try {
      (handler as (d: unknown) => void)(data);
    } catch (err) {
      console.error(`[workflow-sse] Error in handler ${handlerName}:`, err);
    }
  }
}

export function startWorkflow(
  req: StartWorkflowRequest,
  callbacks: WorkflowStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/workflows/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError({ message: `Gateway error: ${detail}` });
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError({ message: "No response body" });
        return;
      }
      _parseSSEStream(reader, callbacks);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Workflow error: ${(e as Error).message}` });
      }
    }
  })();

  return controller;
}

export function resumeWorkflow(
  workflowId: string,
  approved: boolean,
  feedback: string,
  callbacks: WorkflowStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/workflows/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow_id: workflowId, approved, feedback }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError({ message: `Resume error: ${detail}` });
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError({ message: "No response body" });
        return;
      }
      _parseSSEStream(reader, callbacks);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Resume error: ${(e as Error).message}` });
      }
    }
  })();

  return controller;
}

export async function getWorkflowState(workflowId: string): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${GATEWAY_URL}/api/workflows/${encodeURIComponent(workflowId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function cancelWorkflow(workflowId: string): Promise<void> {
  await fetch(`${GATEWAY_URL}/api/workflows/${encodeURIComponent(workflowId)}/cancel`, {
    method: "POST",
  });
}

export async function classifyIntent(message: string): Promise<{ type: string }> {
  const res = await fetch(`${GATEWAY_URL}/api/workflows/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) return { type: "simple_chat" };
  return res.json();
}

// ─── New Workflow APIs ───

export function answerClarification(
  workflowId: string,
  answers: Array<{ id: string; answer: string }>,
  callbacks: WorkflowStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/workflows/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow_id: workflowId, answers }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError({ message: `Answer error: ${detail}` });
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError({ message: "No response body" });
        return;
      }
      _parseSSEStream(reader, callbacks);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Answer error: ${(e as Error).message}` });
      }
    }
  })();

  return controller;
}

export async function getWorkflowTypes(): Promise<{ types: Array<{
  type: string;
  description: string;
  category: string;
  icon: string;
  agent_count: number;
  has_approval_gates: boolean;
}> }> {
  const res = await fetch(`${GATEWAY_URL}/api/workflows/types`);
  if (!res.ok) return { types: [] };
  return res.json();
}

export async function getWorkflowGraph(workflowType: string): Promise<{
  nodes: WorkflowGraphNode[];
  edges: WorkflowGraphEdge[];
  entry: string;
} | null> {
  const res = await fetch(`${GATEWAY_URL}/api/workflows/graph/${encodeURIComponent(workflowType)}`);
  if (!res.ok) return null;
  return (await res.json()) as {
    nodes: WorkflowGraphNode[];
    edges: WorkflowGraphEdge[];
    entry: string;
  };
}

export async function getWorkflowHistory(workflowId: string): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${GATEWAY_URL}/api/workflows/${encodeURIComponent(workflowId)}/history`);
  if (!res.ok) return null;
  return res.json();
}

export function retryWorkflowStep(
  workflowId: string,
  stepId: string,
  callbacks: WorkflowStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/workflows/${encodeURIComponent(workflowId)}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_id: stepId }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError({ message: `Retry error: ${detail}` });
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError({ message: "No response body" });
        return;
      }
      _parseSSEStream(reader, callbacks);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Retry error: ${(e as Error).message}` });
      }
    }
  })();

  return controller;
}

export function skipWorkflowStep(
  workflowId: string,
  stepId: string,
  reason: string,
  callbacks: WorkflowStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/workflows/${encodeURIComponent(workflowId)}/skip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_id: stepId, reason }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text();
        callbacks.onError({ message: `Skip error: ${detail}` });
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError({ message: "No response body" });
        return;
      }
      _parseSSEStream(reader, callbacks);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        callbacks.onError({ message: `Skip error: ${(e as Error).message}` });
      }
    }
  })();

  return controller;
}
