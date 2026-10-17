import {
  getAvailableDropdownOptions,
  humanizeFieldId,
} from "./formFieldState";
import type { AgentFieldType, FieldValue, PdfField } from "./formTypes";

type FieldControlProps = {
  autoFocus?: boolean;
  field: PdfField;
  inputId: string;
  value: FieldValue | undefined;
  onChange: (value: FieldValue) => void;
};

export function FieldControl({
  autoFocus = false,
  field,
  inputId,
  value,
  onChange,
}: FieldControlProps) {
  const label = field.label || humanizeFieldId(field.id);

  if (!field.supported || !field.editable) {
    return (
      <div className="unsupported-field">
        <span>
          <span className="field-label">{label}</span>
          <code>{field.id}</code>
        </span>
        <small>
          {field.capability_reason ??
            `${field.type} is not editable in this form.`}
        </small>
      </div>
    );
  }

  if (field.type === "text") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <input
          autoFocus={autoFocus}
          id={inputId}
          type="text"
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
          autoComplete="off"
        />
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "textarea") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <textarea
          autoFocus={autoFocus}
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        />
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "number") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <input
          autoFocus={autoFocus}
          id={inputId}
          type="number"
          inputMode="decimal"
          step="0.01"
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
          autoComplete="off"
        />
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "dropdown") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <select
          autoFocus={autoFocus}
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="" disabled>
            Select an option
          </option>
          {getAvailableDropdownOptions(field.options).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "checkbox") {
    return (
      <label className="checkbox-control" htmlFor={inputId}>
        <input
          autoFocus={autoFocus}
          id={inputId}
          type="checkbox"
          checked={typeof value === "boolean" ? value : false}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>
          <span className="field-label">{label}</span>
          <code>{field.id}</code>
        </span>
      </label>
    );
  }

  if (field.type === "radio") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <select
          autoFocus={autoFocus}
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="" disabled>
            Select an option
          </option>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <code>{field.id}</code>
      </label>
    );
  }

  return (
    <div className="unsupported-field">
      <span>
        <span className="field-label">{label}</span>
        <code>{field.id}</code>
      </span>
      <small>{field.type} is not supported in this milestone.</small>
    </div>
  );
}

type ProposalValueEditorProps = {
  field: PdfField & { type: AgentFieldType };
  value: FieldValue;
  onChange: (value: FieldValue) => void;
};

export function ProposalValueEditor({
  field,
  value,
  onChange,
}: ProposalValueEditorProps) {
  const inputId = "agent-proposal-value";

  if (field.type === "checkbox") {
    return (
      <fieldset className="agent-proposal-choice">
        <legend>Edit proposed answer</legend>
        <label>
          <input
            type="radio"
            name={inputId}
            checked={value === true}
            onChange={() => onChange(true)}
          />
          Yes
        </label>
        <label>
          <input
            type="radio"
            name={inputId}
            checked={value === false}
            onChange={() => onChange(false)}
          />
          No
        </label>
      </fieldset>
    );
  }

  if (field.type === "dropdown") {
    return (
      <label className="agent-proposal-input" htmlFor={inputId}>
        <span>Edit proposed answer</span>
        <select
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        >
          {getAvailableDropdownOptions(field.options).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (field.type === "textarea") {
    return (
      <label className="agent-proposal-input" htmlFor={inputId}>
        <span>Edit proposed answer</span>
        <textarea
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    );
  }

  return (
    <label className="agent-proposal-input" htmlFor={inputId}>
      <span>Edit proposed answer</span>
      <input
        id={inputId}
        type="text"
        inputMode={field.type === "number" ? "decimal" : undefined}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="off"
      />
    </label>
  );
}
