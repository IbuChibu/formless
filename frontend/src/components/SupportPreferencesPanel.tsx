import { useEffect, useState } from "react";

import {
  assistanceNeedOptions,
  assistancePreferenceLabels,
} from "../assistancePreferences";
import type {
  AssistanceNeed,
  AssistancePreferences,
  SupportIntroductionStatus,
} from "../formTypes";

type SupportPreferencesPanelProps = {
  disabled: boolean;
  preferences: AssistancePreferences;
  status: SupportIntroductionStatus;
  onSave: (preferences: AssistancePreferences) => void;
  onSkip: () => void;
};

export default function SupportPreferencesPanel({
  disabled,
  preferences,
  status,
  onSave,
  onSkip,
}: SupportPreferencesPanelProps) {
  const [isEditing, setIsEditing] = useState(status === "pending");
  const [draft, setDraft] = useState(preferences);

  useEffect(() => {
    setDraft(preferences);
    setIsEditing(status === "pending");
  }, [preferences, status]);

  const labels = assistancePreferenceLabels(preferences);
  const otherNeedsNote =
    draft.support_needs.includes("other") && !draft.other_note?.trim();

  function toggleNeed(need: AssistanceNeed, checked: boolean) {
    setDraft((current) => {
      const supportNeeds = checked
        ? [...current.support_needs, need]
        : current.support_needs.filter((candidate) => candidate !== need);
      return {
        ...current,
        support_needs: supportNeeds,
        other_note:
          need === "other" && !checked
            ? null
            : need === "other" && checked
              ? current.other_note ?? ""
              : current.other_note,
      };
    });
  }

  if (!isEditing) {
    return (
      <section
        className="support-preferences-summary"
        aria-labelledby="support-preferences-summary-heading"
      >
        <div>
          <span>Your support choices</span>
          <strong id="support-preferences-summary-heading">
            {status === "skipped" || labels.length === 0
              ? "Standard guided help"
              : "I’ll adapt how I help"}
          </strong>
          <p>
            {status === "skipped" || labels.length === 0
              ? "You can personalise the pace and wording at any time."
              : "These choices change how help is presented, never what is written into the form."}
          </p>
        </div>
        {labels.length > 0 ? (
          <ul aria-label="Selected support preferences">
            {labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        ) : null}
        <button
          type="button"
          disabled={disabled}
          onClick={() => setIsEditing(true)}
        >
          {status === "skipped" || labels.length === 0
            ? "Personalise help"
            : "Change support"}
        </button>
      </section>
    );
  }

  return (
    <form
      className="support-preferences-panel"
      aria-labelledby="support-preferences-heading"
      onSubmit={(event) => {
        event.preventDefault();
        if (otherNeedsNote) {
          return;
        }
        onSave({
          ...draft,
          other_note: draft.other_note?.trim() || null,
        });
        setIsEditing(false);
      }}
    >
      <div className="support-preferences-heading">
        <span>Before we begin</span>
        <h3 id="support-preferences-heading">
          How can I make this easier for you today?
        </h3>
        <p>
          Choose any that help. This only changes how the assistant explains
          things during this form.
        </p>
      </div>

      <fieldset className="support-needs-grid" disabled={disabled}>
        <legend>How you would like help</legend>
        {assistanceNeedOptions.map((option) => (
          <label key={option.value}>
            <input
              type="checkbox"
              checked={draft.support_needs.includes(option.value)}
              onChange={(event) =>
                toggleNeed(option.value, event.target.checked)
              }
            />
            <span>
              <strong>{option.label}</strong>
              <small>{option.description}</small>
            </span>
          </label>
        ))}
      </fieldset>

      {draft.support_needs.includes("other") ? (
        <label className="support-other-note" htmlFor="support-other-note">
          <span>Your short note</span>
          <textarea
            id="support-other-note"
            maxLength={200}
            required
            value={draft.other_note ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                other_note: event.target.value,
              }))
            }
            placeholder="For example: pause after longer explanations"
          />
          <small>{draft.other_note?.length ?? 0}/200 characters</small>
        </label>
      ) : null}

      <fieldset className="support-input-choice" disabled={disabled}>
        <legend>How would you rather answer?</legend>
        {[
          ["no_preference", "No preference"],
          ["voice", "I’d rather speak"],
          ["typing", "I’d rather type"],
        ].map(([value, label]) => (
          <label key={value}>
            <input
              type="radio"
              name="support-input-mode"
              value={value}
              checked={draft.interaction_mode === value}
              onChange={() =>
                setDraft((current) => ({
                  ...current,
                  interaction_mode:
                    value as AssistancePreferences["interaction_mode"],
                }))
              }
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>

      <p className="support-preferences-safety">
        Choosing voice does not turn on your microphone. Voice starts only when
        you select <strong>Start conversation</strong>.
      </p>

      <div className="support-preferences-actions">
        <button type="submit" disabled={disabled || otherNeedsNote}>
          Save and continue
        </button>
        {status === "pending" ? (
          <button type="button" disabled={disabled} onClick={onSkip}>
            Skip this
          </button>
        ) : (
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              setDraft(preferences);
              setIsEditing(false);
            }}
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

