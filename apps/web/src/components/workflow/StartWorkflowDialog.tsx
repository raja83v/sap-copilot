import { useState } from "react";
import { WORKFLOW_TYPE_LABELS } from "@sap-copilot/shared";
import type { WorkflowType } from "@sap-copilot/shared";

interface StartWorkflowDialogProps {
  workflowType: string;
  open: boolean;
  onClose: () => void;
  onStart: (type: string, request: string) => void;
}

export function StartWorkflowDialog({ workflowType, open, onClose, onStart }: StartWorkflowDialogProps) {
  const [request, setRequest] = useState("");

  if (!open) return null;

  const label = WORKFLOW_TYPE_LABELS[workflowType as WorkflowType] ?? workflowType;

  const handleStart = () => {
    if (!request.trim()) return;
    onStart(workflowType, request.trim());
    setRequest("");
    onClose();
  };

  return (
    <div
      className="workspace-modal-backdrop"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="workspace-modal workspace-modal--medium"
      >
        {/* Header */}
        <div className="workspace-modal__header">
          <div>
            <div className="workspace-modal__eyebrow">Workflow launch</div>
            <h3 className="workspace-modal__title">
            Start Workflow: {label}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="workspace-modal__close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="workspace-modal__body">
          <p className="workspace-modal__copy">
            Describe the business or technical outcome you want. The planner will prepare an orchestration plan and route it through approvals when needed.
          </p>
          <label className="workspace-modal__label">
            Describe what you want to build
          </label>
          <textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder={`e.g., "Create a report that lists all sales orders for a given customer..."`}
            rows={5}
            className="workspace-modal__textarea"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                handleStart();
              }
            }}
          />
          <div className="workspace-modal__hint">
            The Planner agent will analyse your request and propose a step-by-step plan for your approval.
            Press Ctrl+Enter to start.
          </div>
        </div>

        {/* Footer */}
        <div className="workspace-modal__footer">
          <button
            onClick={onClose}
            className="workspace-modal__button workspace-modal__button--secondary"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!request.trim()}
            className="workspace-modal__button workspace-modal__button--primary"
          >
            🚀 Start Workflow
          </button>
        </div>
      </div>
    </div>
  );
}
