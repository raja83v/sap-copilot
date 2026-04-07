import { useCallback } from "react";
import { useAppStore } from "@/stores/appStore";
import {
  startWorkflow as gatewayStartWorkflow,
  resumeWorkflow as gatewayResumeWorkflow,
  answerClarification as gatewayAnswerClarification,
  cancelWorkflow as gatewayCancelWorkflow,
  retryWorkflowStep as gatewayRetryStep,
  skipWorkflowStep as gatewaySkipStep,
  type WorkflowStreamCallbacks,
} from "@/lib/gateway";

/**
 * Hook for workflow operations — start, resume, answer, cancel, retry, skip.
 * Wires up SSE callbacks to the app store for real-time UI updates.
 */
export function useWorkflow() {
  const {
    activeSystemId,
    activeSessionId,
    setActiveWorkflow,
    setActiveWorkflowAgent,
    setPendingApproval,
    setPendingClarification,
    incrementWorkflowNotifications,
  } = useAppStore();

  const makeCallbacks = useCallback(
    (overrides?: Partial<WorkflowStreamCallbacks>): WorkflowStreamCallbacks => ({
      onWorkflowStart: (data) => {
        // Don't call setActiveWorkflow with LangGraph UUID — it's not a Convex ID.
        // The workflow will appear in the sidebar via Convex reactivity.
        overrides?.onWorkflowStart?.(data);
      },
      onAgentStart: (data) => {
        setActiveWorkflowAgent(data.agent);
        overrides?.onAgentStart?.(data);
      },
      onAgentEnd: (data) => {
        setActiveWorkflowAgent(null);
        overrides?.onAgentEnd?.(data);
      },
      onContent: (data) => {
        overrides?.onContent?.(data);
      },
      onToolStart: (data) => {
        overrides?.onToolStart?.(data);
      },
      onToolEnd: (data) => {
        overrides?.onToolEnd?.(data);
      },
      onStepComplete: (data) => {
        overrides?.onStepComplete?.(data);
      },
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
        overrides?.onApprovalRequired?.(data);
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
        overrides?.onClarificationRequired?.(data);
      },
      onWorkflowPaused: (data) => {
        overrides?.onWorkflowPaused?.(data);
      },
      onWorkflowResumed: (data) => {
        overrides?.onWorkflowResumed?.(data);
      },
      onWorkflowComplete: (data) => {
        setActiveWorkflowAgent(null);
        overrides?.onWorkflowComplete?.(data);
      },
      onError: (data) => {
        console.error("Workflow error:", data.message);
        overrides?.onError?.(data);
      },
    }),
    [setActiveWorkflow, setActiveWorkflowAgent, setPendingApproval, setPendingClarification, incrementWorkflowNotifications],
  );

  const start = useCallback(
    (type: string, request: string, overrides?: Partial<WorkflowStreamCallbacks>) => {
      if (!activeSystemId || !activeSessionId) return null;
      return gatewayStartWorkflow(
        {
          system_id: activeSystemId,
          session_id: activeSessionId,
          workflow_type: type,
          user_request: request,
        },
        makeCallbacks(overrides),
      );
    },
    [activeSystemId, activeSessionId, makeCallbacks],
  );

  const resume = useCallback(
    (workflowId: string, approved: boolean, feedback: string, overrides?: Partial<WorkflowStreamCallbacks>) => {
      return gatewayResumeWorkflow(workflowId, approved, feedback, makeCallbacks(overrides));
    },
    [makeCallbacks],
  );

  const answer = useCallback(
    (workflowId: string, answers: Array<{ id: string; answer: string }>, overrides?: Partial<WorkflowStreamCallbacks>) => {
      setPendingClarification(null);
      return gatewayAnswerClarification(workflowId, answers, makeCallbacks(overrides));
    },
    [makeCallbacks, setPendingClarification],
  );

  const cancel = useCallback(
    async (workflowId: string) => {
      await gatewayCancelWorkflow(workflowId);
    },
    [],
  );

  const retry = useCallback(
    (workflowId: string, stepId: string, overrides?: Partial<WorkflowStreamCallbacks>) => {
      return gatewayRetryStep(workflowId, stepId, makeCallbacks(overrides));
    },
    [makeCallbacks],
  );

  const skip = useCallback(
    (workflowId: string, stepId: string, reason: string, overrides?: Partial<WorkflowStreamCallbacks>) => {
      return gatewaySkipStep(workflowId, stepId, reason, makeCallbacks(overrides));
    },
    [makeCallbacks],
  );

  return { start, resume, answer, cancel, retry, skip };
}
