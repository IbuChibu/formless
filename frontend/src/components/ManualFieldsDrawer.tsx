import { FieldControl } from "../FieldControls";
import { humanizeFieldId, isExplainableField } from "../formFieldState";
import type {
  AgentRequestField,
  AgentStatus,
  FieldValue,
  PageFieldGroup,
} from "../formTypes";

type ManualFieldsDrawerProps = {
  activeFieldId: string | null;
  agentFields: AgentRequestField[];
  agentStatus: AgentStatus;
  fieldCount: number;
  fieldGroups: PageFieldGroup[];
  formValues: Record<string, FieldValue>;
  isOpen: boolean;
  isReady: boolean;
  hasPendingProposal: boolean;
  onAskForExplanation: (fieldId: string, message: string) => void;
  onChangeField: (fieldId: string, value: FieldValue) => void;
  onToggle: () => void;
};

export default function ManualFieldsDrawer({
  activeFieldId,
  agentFields,
  agentStatus,
  fieldCount,
  fieldGroups,
  formValues,
  isOpen,
  isReady,
  hasPendingProposal,
  onAskForExplanation,
  onChangeField,
  onToggle,
}: ManualFieldsDrawerProps) {
  return (
    <section className="manual-fields-drawer">
      <button
        className="manual-drawer-toggle"
        type="button"
        aria-controls="manual-fields-panel"
        aria-expanded={isOpen}
        disabled={!isReady || fieldCount === 0}
        onClick={onToggle}
      >
        <span className="manual-drawer-copy">
          <strong>Edit all fields</strong>
          <small>
            Manual fallback{fieldCount > 0 ? ` · ${fieldCount} fields` : ""}
          </small>
        </span>
        <span
          className={`manual-drawer-chevron${isOpen ? " open" : ""}`}
          aria-hidden="true"
        >
          ⌄
        </span>
      </button>

      <div
        className="fields-content manual-fields-content"
        id="manual-fields-panel"
        hidden={!isOpen}
      >
        {isReady ? (
          <form
            className="field-list"
            onSubmit={(event) => event.preventDefault()}
          >
            {fieldGroups.map((group) => (
              <section
                className="field-page-group"
                key={group.page ?? "other"}
              >
                <h3 className="field-page-heading">
                  {group.page ? `Page ${group.page}` : "Other fields"}
                </h3>
                <div className="page-field-list">
                  {group.fields.map(({ field, index }) => {
                    const isActiveForAgent = activeFieldId === field.id;
                    const agentFieldState = agentFields.find(
                      (candidate) => candidate.id === field.id,
                    );
                    const isAskingAgent =
                      isActiveForAgent && agentStatus === "loading";

                    return (
                      <div
                        className={`field-item${
                          isActiveForAgent ? " active-for-agent" : ""
                        }`}
                        key={field.id}
                      >
                        <FieldControl
                          field={field}
                          inputId={`pdf-field-${index}`}
                          value={formValues[field.id]}
                          onChange={(value) => onChangeField(field.id, value)}
                        />
                        {isExplainableField(field) ? (
                          <button
                            className="explain-field-button"
                            type="button"
                            disabled={
                              agentStatus === "loading" ||
                              hasPendingProposal ||
                              agentFieldState?.status !== "unanswered"
                            }
                            aria-label={`Explain ${
                              field.label || humanizeFieldId(field.id)
                            } with AI`}
                            onClick={() =>
                              onAskForExplanation(
                                field.id,
                                "Please explain this field in plain language.",
                              )
                            }
                          >
                            <span aria-hidden="true">✦</span>
                            {isAskingAgent ? "Asking…" : "Explain with AI"}
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </form>
        ) : null}
      </div>
    </section>
  );
}
