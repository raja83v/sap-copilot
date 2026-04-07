import { useState, useCallback, useRef } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../../../convex/_generated/api";
import { useAppStore } from "@/stores/appStore";
import { streamChat, resumeWorkflow, answerClarification } from "@/lib/gateway";
import type { ChatMessage, ToolCall } from "@sap-copilot/shared";
import type { Id } from "../../../../convex/_generated/dataModel";

/** Map a Convex message doc to the shared ChatMessage type. */
function toChat(doc: {
  _id: string;
  sessionId: string;
  role: string;
  content: string;
  toolCalls?: { id: string; name: string; parameters: string; result?: string; duration?: number; status: string }[];
  timestamp: number;
}): ChatMessage {
  return {
    id: doc._id,
    sessionId: doc.sessionId,
    role: doc.role as ChatMessage["role"],
    content: doc.content,
    timestamp: doc.timestamp,
    toolCalls: doc.toolCalls?.map((tc) => ({
      id: tc.id,
      name: tc.name,
      parameters: safeParse(tc.parameters),
      result: tc.result,
      duration: tc.duration,
      status: tc.status as ToolCall["status"],
    })),
  };
}

function safeParse(json: string): Record<string, unknown> {
  try { return JSON.parse(json); } catch { return {}; }
}

/**
 * Core chat hook — reads messages from Convex, sends via gateway SSE.
 */
export function useChatMessages(sessionId: string | null) {
  const { activeSystemId, selectedModel, setIsStreaming, setActiveWorkflow, setActiveWorkflowAgent } = useAppStore();

  // Persisted messages from Convex
  const convexMessages = useQuery(
    api.messages.listBySession,
    sessionId ? { sessionId: sessionId as Id<"sessions"> } : "skip",
  );

  // Streaming assistant message (in-progress, not yet saved)
  const [streamingMsg, setStreamingMsg] = useState<ChatMessage | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Convex mutations
  const addMessage = useMutation(api.messages.add);
  const incrementCounters = useMutation(api.sessions.incrementCounters);

  // Merge persisted + streaming
  const messages: ChatMessage[] = [
    ...(convexMessages?.map(toChat) ?? []),
    ...(streamingMsg ? [streamingMsg] : []),
  ];

  const sendMessage = useCallback(
    async (content: string, sessionIdOverride?: string) => {
      const effectiveSessionId = sessionIdOverride || sessionId;
      if (!content.trim() || !effectiveSessionId || !activeSystemId) return;

      // Declare outside try so finalize() can access them
      let fullContent = "";
      const toolCalls: ToolCall[] = [];

      async function finalize() {
        setIsStreaming(false);

        // Persist assistant message
        const serializedCalls = toolCalls.length
          ? toolCalls.map((tc) => ({
              id: tc.id,
              name: tc.name,
              parameters: JSON.stringify(tc.parameters),
              result: tc.result,
              duration: tc.duration,
              status: tc.status,
            }))
          : undefined;

        try {
          await addMessage({
            sessionId: effectiveSessionId as Id<"sessions">,
            role: "assistant",
            content: fullContent,
            toolCalls: serializedCalls,
            model: selectedModel,
          });
          await incrementCounters({
            id: effectiveSessionId as Id<"sessions">,
            messages: 1,
            toolCalls: toolCalls.length || undefined,
          });
        } catch (e) {
          console.error("Failed to persist assistant message:", e);
        }

        setStreamingMsg(null);
      }

      try {
        // 1. Persist user message
        await addMessage({
          sessionId: effectiveSessionId as Id<"sessions">,
          role: "user",
          content,
        });
        await incrementCounters({ id: effectiveSessionId as Id<"sessions">, messages: 1 });

        // 2. Build conversation history for gateway
        const history = [
          ...(convexMessages?.map((m) => ({
            role: m.role as "user" | "assistant",
            content: m.content,
          })) ?? []),
          { role: "user" as const, content },
        ];

        // 3. Start streaming
        setIsStreaming(true);
        const assistantId = crypto.randomUUID();

        setStreamingMsg({
          id: assistantId,
          sessionId: effectiveSessionId,
          role: "assistant",
          content: "",
          timestamp: Date.now(),
          toolCalls: [],
          status: "streaming",
        });

        abortRef.current = streamChat(activeSystemId, history, selectedModel, {
          onContent(text) {
            fullContent += text;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
          },
          onToolStart(data) {
            const tc: ToolCall = {
              id: data.id,
              name: data.name,
              parameters: data.parameters,
              status: "running",
            };
            toolCalls.push(tc);
            setStreamingMsg((prev) =>
              prev ? { ...prev, toolCalls: [...toolCalls] } : null,
            );
          },
          onToolEnd(data) {
            const idx = toolCalls.findIndex((t) => t.id === data.id);
            if (idx >= 0) {
              toolCalls[idx] = {
                ...toolCalls[idx],
                result: data.result,
                duration: data.duration,
                status: data.status as ToolCall["status"],
              };
              setStreamingMsg((prev) =>
                prev ? { ...prev, toolCalls: [...toolCalls] } : null,
              );
            }
          },
          onError(message) {
            fullContent += `\n\n**Error:** ${message}`;
            finalize();
          },
          onDone(doneContent) {
            if (doneContent) fullContent = doneContent;
            finalize();
          },
          // Workflow events — triggered when intent classifier routes to LangGraph
          onWorkflowStart(data) {
            // Don't call setActiveWorkflow with the LangGraph UUID — it's not
            // a Convex document ID. The workflow will appear in the sidebar
            // once the Convex document is created by the gateway.
            // Store the LangGraph workflow ID for reference but don't switch views.
            useAppStore.getState().resetWorkflowProgress();
            fullContent += `\n\n🔄 **Workflow started** — ${data.type}\n`;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
          },
          onAgentStart(data) {
            setActiveWorkflowAgent(data.agent);
            useAppStore.getState().addWorkflowStep(data.agent);
            useAppStore.getState().setWorkflowStreamingContent("");
            fullContent += `\n🤖 **${data.agent}** agent started...\n`;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
          },
          onAgentEnd(data) {
            setActiveWorkflowAgent(null);
            const extra = data as Record<string, unknown>;
            const step = extra.step as Record<string, unknown> | undefined;
            useAppStore.getState().completeWorkflowStep(data.agent, data.phase, step?.tool_call_count as number | undefined);
            const action = (extra.action as string) || "processing";
            const toolCount = (step?.tool_call_count as number) || 0;
            fullContent += `\n\u2705 **${data.agent}** completed — ${action} (${toolCount} tool calls)\n`;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
          },
          onApprovalRequired(data) {
            // Store approval data — the ChatPanel will render an inline approval card
            const approvalDetails = typeof data.data === "object" ? data.data : {};
            const detailsText = (approvalDetails as Record<string, unknown>).details as string
              || (approvalDetails as Record<string, unknown>).phase as string
              || JSON.stringify(data.data);
            useAppStore.getState().setPendingApproval({
              workflow_id: data.workflow_id,
              id: (approvalDetails as Record<string, unknown>).approval_id as string || "",
              phase: (approvalDetails as Record<string, unknown>).phase as string || "",
              details: detailsText,
              status: "pending",
              requestedAt: Date.now(),
            });
            // Don't add text to chat — the inline approval card will show instead
          },
          onClarificationRequired(data) {
            // Store clarification data — the ChatPanel will render an inline dialog
            useAppStore.getState().setPendingClarification({
              workflow_id: data.workflow_id,
              questions: data.questions.map((q) => ({
                id: q.id,
                question: q.question,
                type: (q.question_type || "text") as "text" | "select" | "confirm",
                options: q.options,
                required: q.required,
              })),
            });
            // Don't add text to chat — the inline clarification card will show instead
          },
          onStepComplete(data) {
            fullContent += `\n📌 **${data.agent}** completed — ${data.action} (${data.tool_calls} tool calls)\n`;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
          },
          onWorkflowPaused() {
            // Workflow is waiting for approval/clarification — finalize the chat message
            finalize();
          },
          onWorkflowComplete(_data) {
            // Keep timeline visible — just clear active agent
            useAppStore.getState().setActiveWorkflowAgent(null);
            fullContent += `\n\n🎉 **Workflow completed!**\n`;
            setStreamingMsg((prev) =>
              prev ? { ...prev, content: fullContent } : null,
            );
            // Don't call setActiveWorkflow with LangGraph UUID — the workflow
            // is visible in the sidebar via Convex reactivity.
          },
        }, effectiveSessionId);
      } catch (e) {
        setIsStreaming(false);
        setStreamingMsg(null);
        console.error("sendMessage failed:", e);
      }
    },
    [sessionId, activeSystemId, selectedModel, convexMessages, addMessage, incrementCounters, setIsStreaming, setActiveWorkflow, setActiveWorkflowAgent],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setStreamingMsg(null);
  }, [setIsStreaming]);

  // ------------------------------------------------------------------
  // Resume helpers — reuse the same streaming message pattern so the
  // chat keeps updating after approval / clarification.
  // ------------------------------------------------------------------

  /** Build workflow-aware callbacks that write into a streaming message. */
  const makeStreamingResumeCallbacks = useCallback(
    (finalizeFn: () => Promise<void>, fullContentRef: { value: string }) => {
      const store = useAppStore.getState;
      return {
        onWorkflowStart() {},
        onWorkflowResumed() {
          store().setIsStreaming(true);
        },
        onAgentStart(data: { agent: string }) {
          store().addWorkflowStep(data.agent);
          store().setWorkflowStreamingContent("");
          fullContentRef.value += `\n🤖 **${data.agent}** agent started...\n`;
          setStreamingMsg((prev) =>
            prev ? { ...prev, content: fullContentRef.value } : null,
          );
        },
        onAgentEnd(data: { agent: string; phase: string; step?: Record<string, unknown> }) {
          const toolCount = (data.step?.tool_call_count as number) || 0;
          store().completeWorkflowStep(data.agent, data.phase, toolCount);
          fullContentRef.value += `\n✅ **${data.agent}** completed — ${data.phase || "done"} (${toolCount} tool calls)\n`;
          setStreamingMsg((prev) =>
            prev ? { ...prev, content: fullContentRef.value } : null,
          );
        },
        onContent(data: { text: string }) {
          store().appendWorkflowContent(data.text);
          fullContentRef.value += data.text;
          setStreamingMsg((prev) =>
            prev ? { ...prev, content: fullContentRef.value } : null,
          );
        },
        onToolStart() {},
        onToolEnd() {},
        onStepComplete(data: { agent: string; action: string; tool_calls: number }) {
          fullContentRef.value += `\n📌 **${data.agent}** — ${data.action} (${data.tool_calls} tools)\n`;
          setStreamingMsg((prev) =>
            prev ? { ...prev, content: fullContentRef.value } : null,
          );
        },
        onApprovalRequired(data: { workflow_id: string; data: Record<string, unknown> }) {
          const approvalDetails = typeof data.data === "object" ? data.data : {};
          const detailsText = (approvalDetails as Record<string, unknown>).details as string
            || (approvalDetails as Record<string, unknown>).phase as string
            || JSON.stringify(data.data);
          store().setPendingApproval({
            workflow_id: data.workflow_id,
            id: (approvalDetails as Record<string, unknown>).approval_id as string || "",
            phase: (approvalDetails as Record<string, unknown>).phase as string || "",
            details: detailsText,
            status: "pending",
            requestedAt: Date.now(),
          });
          store().incrementWorkflowNotifications();
        },
        onClarificationRequired(data: { workflow_id: string; questions: Array<{ id: string; question: string; question_type: string; options?: string[]; required: boolean }> }) {
          store().setPendingClarification({
            workflow_id: data.workflow_id,
            questions: data.questions.map((q) => ({
              id: q.id,
              question: q.question,
              type: (q.question_type || "text") as "text" | "select" | "confirm",
              options: q.options,
              required: q.required,
            })),
          });
          store().incrementWorkflowNotifications();
        },
        onWorkflowPaused() {
          finalizeFn();
        },
        onWorkflowComplete(data: Record<string, unknown>) {
          store().setActiveWorkflowAgent(null);
          // Build a summary from the workflow_complete payload
          const objects = data.created_objects as string[] | undefined;
          if (objects && objects.length > 0) {
            fullContentRef.value += `\n\n🎉 **Workflow completed!**\n\n**Created objects:** ${objects.join(", ")}\n`;
          } else {
            fullContentRef.value += `\n\n🎉 **Workflow completed!**\n`;
          }
          if (data.review_pass != null) {
            fullContentRef.value += `**Review:** ${data.review_pass ? "✅ Passed" : "⚠️ Issues found"}\n`;
          }
          if (data.tests_pass != null) {
            fullContentRef.value += `**Tests:** ${data.tests_pass ? "✅ Passed" : "⚠️ Issues found"}\n`;
          }
          setStreamingMsg((prev) =>
            prev ? { ...prev, content: fullContentRef.value } : null,
          );
          finalizeFn();
        },
        onError(data: { message: string }) {
          const currentAgent = store().activeWorkflowAgent;
          if (currentAgent) store().failWorkflowStep(currentAgent);
          fullContentRef.value += `\n\n**Error:** ${data.message}`;
          finalizeFn();
        },
      };
    },
    [setStreamingMsg],
  );

  /** Resume a paused workflow after user approval — creates a new streaming message. */
  const resumeChat = useCallback(
    (workflowId: string, approved: boolean, feedback: string) => {
      if (!sessionId) return;
      const effectiveSessionId = sessionId;

      const fullContentRef = { value: "" };
      const assistantId = crypto.randomUUID();
      setIsStreaming(true);
      setStreamingMsg({
        id: assistantId,
        sessionId: effectiveSessionId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        status: "streaming",
      });

      async function finalize() {
        setIsStreaming(false);
        try {
          if (fullContentRef.value.trim()) {
            await addMessage({
              sessionId: effectiveSessionId as Id<"sessions">,
              role: "assistant",
              content: fullContentRef.value,
              model: selectedModel,
            });
          }
        } catch (e) {
          console.error("Failed to persist resume message:", e);
        }
        setStreamingMsg(null);
      }

      const callbacks = makeStreamingResumeCallbacks(finalize, fullContentRef);
      resumeWorkflow(workflowId, approved, feedback, callbacks as import("@/lib/gateway").WorkflowStreamCallbacks);
    },
    [sessionId, selectedModel, addMessage, setIsStreaming, makeStreamingResumeCallbacks],
  );

  /** Resume after clarification — creates a new streaming message. */
  const answerChat = useCallback(
    (workflowId: string, answers: Array<{ id: string; answer: string }>) => {
      if (!sessionId) return;
      const effectiveSessionId = sessionId;

      const fullContentRef = { value: "" };
      const assistantId = crypto.randomUUID();
      setIsStreaming(true);
      setStreamingMsg({
        id: assistantId,
        sessionId: effectiveSessionId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        status: "streaming",
      });

      async function finalize() {
        setIsStreaming(false);
        try {
          if (fullContentRef.value.trim()) {
            await addMessage({
              sessionId: effectiveSessionId as Id<"sessions">,
              role: "assistant",
              content: fullContentRef.value,
              model: selectedModel,
            });
          }
        } catch (e) {
          console.error("Failed to persist clarification message:", e);
        }
        setStreamingMsg(null);
      }

      const callbacks = makeStreamingResumeCallbacks(finalize, fullContentRef);
      answerClarification(workflowId, answers, callbacks as import("@/lib/gateway").WorkflowStreamCallbacks);
    },
    [sessionId, selectedModel, addMessage, setIsStreaming, makeStreamingResumeCallbacks],
  );

  return { messages, sendMessage, stopStreaming, resumeChat, answerChat };
}
