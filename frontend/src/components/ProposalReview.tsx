import { ProposalValueEditor } from "../FieldControls";
import { formatAgentValue, humanizeFieldId } from "../formFieldState";
import type {
  AgentStatus,
  FieldValue,
  PdfField,
  PendingProposal,
  ProposalAgentEffect,
} from "../formTypes";

type ProposalReviewProps = {
  agentStatus: AgentStatus;
  canApplyEditedProposal: boolean;
  canUseOriginalProposal: boolean;
  details: ProposalAgentEffect | null;
  field: PdfField & {
    type: "text" | "textarea" | "number" | "dropdown" | "checkbox";
  };
  isEditing: boolean;
  isReplacement: boolean;
  pendingProposal: PendingProposal;
  proposalEditValue: FieldValue;
  onCancelCorrection: () => void;
  onCancelEdit: () => void;
  onChangeEditValue: (value: FieldValue) => void;
  onConfirm: (value: FieldValue) => void;
  onEdit: () => void;
  onReject: () => void;
  onSkip: () => void;
  onUseOriginal: () => void;
};

export default function ProposalReview({
  agentStatus,
  canApplyEditedProposal,
  canUseOriginalProposal,
  details,
  field,
  isEditing,
  isReplacement,
  pendingProposal,
  proposalEditValue,
  onCancelCorrection,
  onCancelEdit,
  onChangeEditValue,
  onConfirm,
  onEdit,
  onReject,
  onSkip,
  onUseOriginal,
}: ProposalReviewProps) {
  return (
    <section
      className="agent-confirmation"
      aria-label="Review proposed answer"
    >
      <div className="agent-confirmation-heading">
        <div>
          <span>{isReplacement ? "Review replacement" : "Review proposal"}</span>
          <strong>
            {field.question || field.label || humanizeFieldId(field.id)}
          </strong>
        </div>
        <span className="agent-confirmation-status">Awaiting your review</span>
      </div>

      {isEditing ? (
        <form
          className="agent-proposal-edit"
          onSubmit={(event) => {
            event.preventDefault();
            if (canApplyEditedProposal) {
              onConfirm(proposalEditValue);
            }
          }}
        >
          <ProposalValueEditor
            field={field}
            value={proposalEditValue}
            onChange={onChangeEditValue}
          />
          <div className="agent-confirmation-actions">
            <button
              className="primary"
              type="submit"
              disabled={agentStatus === "loading" || !canApplyEditedProposal}
            >
              Confirm edited answer
            </button>
            <button
              type="button"
              disabled={agentStatus === "loading"}
              onClick={onCancelEdit}
            >
              Cancel edit
            </button>
          </div>
        </form>
      ) : (
        <>
          {details?.effect === "replacement_proposal" ? (
            <div className="agent-confirmation-value">
              <span>Current confirmed answer</span>
              <strong>
                {formatAgentValue(details.previous_confirmed_value)}
              </strong>
            </div>
          ) : null}
          {details?.transformation ? (
            <div className="agent-preparation-comparison">
              <div>
                <span>You said</span>
                <strong>{formatAgentValue(details.original_value)}</strong>
              </div>
              <div>
                <span>Prepared for the form</span>
                <strong>{formatAgentValue(details.prepared_value)}</strong>
              </div>
              <small>{details.transformation}</small>
            </div>
          ) : (
            <div className="agent-confirmation-value">
              <span>Prepared answer</span>
              <strong>{formatAgentValue(pendingProposal.value)}</strong>
            </div>
          )}
          <p>
            {isReplacement
              ? "Your current confirmed answer and PDF stay unchanged until you confirm this replacement."
              : "This answer has not been added to the PDF. Review it, then confirm or edit it."}
          </p>
          <div className="agent-confirmation-actions">
            <button
              className="primary"
              type="button"
              disabled={agentStatus === "loading"}
              onClick={() => onConfirm(pendingProposal.value)}
            >
              {isReplacement ? "Confirm replacement" : "Confirm"}
            </button>
            <button
              type="button"
              disabled={agentStatus === "loading"}
              onClick={onEdit}
            >
              Edit
            </button>
            {canUseOriginalProposal ? (
              <button
                type="button"
                disabled={agentStatus === "loading"}
                onClick={onUseOriginal}
              >
                Use original
              </button>
            ) : null}
            <button
              type="button"
              disabled={agentStatus === "loading"}
              onClick={onReject}
            >
              Reject
            </button>
            {isReplacement ? (
              <button
                type="button"
                disabled={agentStatus === "loading"}
                onClick={onCancelCorrection}
              >
                Cancel correction
              </button>
            ) : (
              <button
                type="button"
                disabled={agentStatus === "loading"}
                onClick={onSkip}
              >
                Skip field
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
