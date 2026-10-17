import {
  formatReviewValue,
  getReviewStatusLabel,
  humanizeFieldId,
} from "../formFieldState";
import type {
  FieldValue,
  ReviewFieldStatus,
  ReviewItem,
} from "../formTypes";

type FormReviewPanelProps = {
  counts: Record<ReviewFieldStatus, number>;
  formValues: Record<string, FieldValue>;
  items: ReviewItem[];
  proposedFieldId: string | null;
  proposedValue: FieldValue | undefined;
  onClose: () => void;
  onSelectField: (fieldId: string) => void;
};

export default function FormReviewPanel({
  counts,
  formValues,
  items,
  proposedFieldId,
  proposedValue,
  onClose,
  onSelectField,
}: FormReviewPanelProps) {
  return (
    <section
      className="form-review-panel"
      aria-labelledby="form-review-heading"
    >
      <div className="form-review-heading">
        <div>
          <span>Final review</span>
          <h3 id="form-review-heading">Check every form field</h3>
        </div>
        <button type="button" aria-label="Close final review" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="form-review-summary" aria-label="Field status summary">
        <span>
          <strong>{counts.confirmed}</strong> completed
        </span>
        <span>
          <strong>{counts.proposed}</strong> proposed
        </span>
        <span>
          <strong>{counts.skipped}</strong> skipped
        </span>
        <span>
          <strong>{counts.unanswered}</strong> unanswered
        </span>
      </div>
      <div className="form-review-list">
        {items.map(({ field, status }) => {
          const displayedValue =
            field.id === proposedFieldId ? proposedValue : formValues[field.id];
          return (
            <button
              key={field.id}
              type="button"
              className={`form-review-item ${status}`}
              onClick={() => onSelectField(field.id)}
            >
              <span className="form-review-item-copy">
                <strong>
                  {field.question ||
                    field.label ||
                    humanizeFieldId(field.id)}
                </strong>
                <small>
                  {status === "unanswered"
                    ? "No reviewed answer"
                    : status === "skipped"
                      ? "Skipped for now"
                      : formatReviewValue(displayedValue)}
                </small>
              </span>
              <span className={`form-review-status ${status}`}>
                {getReviewStatusLabel(status)}
              </span>
            </button>
          );
        })}
      </div>
      <p>
        Proposed answers are not written to the PDF until you confirm them.
        Select any field to review or edit it on the document.
      </p>
    </section>
  );
}
