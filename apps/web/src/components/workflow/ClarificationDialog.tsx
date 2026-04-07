import { useState } from "react";
import type { ClarificationQuestion } from "@sap-copilot/shared";

interface ClarificationDialogProps {
  open: boolean;
  workflowId: string;
  questions: ClarificationQuestion[];
  onSubmit: (answers: Array<{ id: string; answer: string }>) => void;
  onClose: () => void;
}

export function ClarificationDialog({
  open,
  workflowId: _workflowId,
  questions,
  onSubmit,
  onClose,
}: ClarificationDialogProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});

  if (!open || questions.length === 0) return null;

  const updateAnswer = (id: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  };

  const allRequiredAnswered = questions
    .filter((q) => q.required)
    .every((q) => (answers[q.id] || "").trim().length > 0);

  const handleSubmit = () => {
    const result = questions.map((q) => ({
      id: q.id,
      answer: answers[q.id] || q.default || "",
    }));
    onSubmit(result);
    setAnswers({});
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
            <div className="workspace-modal__eyebrow">Clarification required</div>
            <h3 className="workspace-modal__title">
            Clarification Needed
            </h3>
          </div>
        </div>

        {/* Body */}
        <div className="workspace-modal__body workspace-modal__body--stacked">
          <p className="workspace-modal__copy">
            The AI needs some additional information to proceed. Please answer the following questions:
          </p>

          {questions.map((q, i) => (
            <div key={q.id} className="workspace-modal__field">
              <label className="workspace-modal__label">
                {i + 1}. {q.question}
                {q.required && <span className="workspace-modal__required">*</span>}
              </label>

              {q.type === "select" && q.options ? (
                <select
                  value={answers[q.id] || q.default || ""}
                  onChange={(e) => updateAnswer(q.id, e.target.value)}
                  className="workspace-modal__select"
                >
                  <option value="">Select...</option>
                  {q.options.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : q.type === "confirm" ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => updateAnswer(q.id, "yes")}
                    className={`workspace-modal__choice ${answers[q.id] === "yes" ? "workspace-modal__choice--yes" : ""}`}
                  >
                    ✅ Yes
                  </button>
                  <button
                    onClick={() => updateAnswer(q.id, "no")}
                    className={`workspace-modal__choice ${answers[q.id] === "no" ? "workspace-modal__choice--no" : ""}`}
                  >
                    ❌ No
                  </button>
                </div>
              ) : (
                <input
                  value={answers[q.id] || ""}
                  onChange={(e) => updateAnswer(q.id, e.target.value)}
                  placeholder={q.default || "Type your answer..."}
                  className="workspace-modal__input"
                />
              )}
            </div>
          ))}
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
            onClick={handleSubmit}
            disabled={!allRequiredAnswered}
            className="workspace-modal__button workspace-modal__button--primary"
          >
            Submit Answers
          </button>
        </div>
      </div>
    </div>
  );
}
