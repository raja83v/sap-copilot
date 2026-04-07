import { useState } from "react";
import { Button, FlexBox, Icon, Tag, TextArea } from "@ui5/webcomponents-react";
import type { WorkflowApproval } from "@sap-copilot/shared";

interface ApprovalPanelProps {
  approval: WorkflowApproval;
  onApprove: () => void;
  onReject: (feedback: string) => void;
}

export function ApprovalPanel({ approval, onApprove, onReject }: ApprovalPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  let structuredDetails: Record<string, unknown> | null = null;
  try { structuredDetails = JSON.parse(approval.details); } catch { /* plain text */ }

  return (
    <div className="workflow-action-card workflow-action-card--warning">
      <div className="workflow-action-card__header workflow-action-card__header--warning">
        <Icon name="alert" style={{ fontSize: 16, color: "var(--sapWarningColor)" }} />
        <span className="workflow-action-card__title">Approval Required</span>
        <Tag colorScheme="2">{approval.phase}</Tag>
      </div>
      <div className="workflow-action-card__body">
        {structuredDetails ? (
          <StructuredDetails data={structuredDetails} />
        ) : (
          <div className="sap-code-block" style={{ whiteSpace: "pre-wrap", maxHeight: 280, overflowY: "auto", lineHeight: 1.6 }}>
            {approval.details}
          </div>
        )}

        <div className="workflow-action-card__footer">
          {!showRejectInput ? (
            <FlexBox style={{ gap: 8 }}>
              <Button design="Emphasized" icon="accept" onClick={onApprove}>Approve</Button>
              <Button design="Negative" icon="decline" onClick={() => setShowRejectInput(true)}>Reject</Button>
            </FlexBox>
          ) : (
            <FlexBox direction="Column" style={{ gap: "var(--space-sm)" }}>
              <label className="workflow-action-card__label">
                Rejection feedback (explain what should change):
              </label>
              <TextArea
                value={feedback}
                onInput={(e) => setFeedback((e.target as unknown as HTMLTextAreaElement).value)}
                placeholder="Describe what needs to be changed…"
                rows={3}
                style={{ width: "100%" }}
              />
              <FlexBox style={{ gap: 8 }}>
                <Button design="Negative" onClick={() => onReject(feedback)}>Reject with Feedback</Button>
                <Button design="Transparent" onClick={() => { setShowRejectInput(false); setFeedback(""); }}>Cancel</Button>
              </FlexBox>
            </FlexBox>
          )}
        </div>
      </div>
    </div>
  );
}

function StructuredDetails({ data }: { data: Record<string, unknown> }) {
  const planSteps = data.plan_steps as string[] | undefined;
  const objectsToCreate = data.objects_to_create as string[] | undefined;
  const pkg = data.package as string | undefined;
  const transport = data.transport as string | undefined;

  return (
    <div className="workflow-action-card__sections">
      {planSteps && planSteps.length > 0 && (
        <div>
          <div className="workflow-action-card__section-title">
            <Icon name="task" style={{ fontSize: 11 }} /> Plan Steps
          </div>
          <div className="workflow-action-card__section-surface">
            {planSteps.map((step, i) => (
              <div key={i} className="workflow-action-card__section-row">
                <span className="workflow-action-card__section-index">{i + 1}.</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {objectsToCreate && objectsToCreate.length > 0 && (
        <div>
          <div className="workflow-action-card__section-title">
            <Icon name="attachment" style={{ fontSize: 11 }} /> Objects to Create
          </div>
          <FlexBox wrap="Wrap" style={{ gap: "var(--space-xs)" }}>
            {objectsToCreate.map((obj) => (
              <span key={obj} className="workflow-action-card__object-pill">
                {obj}
              </span>
            ))}
          </FlexBox>
        </div>
      )}

      {(pkg || transport) && (
        <FlexBox style={{ gap: "var(--space-xl)", fontSize: "var(--font-size-sm)" }}>
          {pkg && <div><span className="workflow-action-card__meta-label">Package: </span><code>{pkg}</code></div>}
          {transport && <div><span className="workflow-action-card__meta-label">Transport: </span><code>{transport}</code></div>}
        </FlexBox>
      )}

      {!planSteps && !objectsToCreate && (
        <div className="sap-code-block" style={{ whiteSpace: "pre-wrap", maxHeight: 280, overflowY: "auto", lineHeight: 1.6 }}>
          {JSON.stringify(data, null, 2)}
        </div>
      )}
    </div>
  );
}
