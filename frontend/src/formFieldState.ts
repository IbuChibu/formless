import type {
  AgentFieldStatus,
  AgentFieldType,
  AgentRequest,
  AgentRequestField,
  ConversationMessage,
  ConversationPhase,
  ConversationState,
  FieldValue,
  PageFieldGroup,
  PdfField,
  ReviewFieldStatus,
  WebGuidanceCitation,
} from "./formTypes";

const numberPattern = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;
const groupedNumberPattern = /^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?$/;
const dropdownPlaceholderPattern =
  /^(?:please\s+)?(?:select|choose)(?:\s+(?:one|an?\s+option))?$/i;

export function humanizeFieldId(fieldId: string): string {
  const words = fieldId.replace(/[._-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function isExplainableField(
  field: PdfField,
): field is PdfField & { type: AgentFieldType } {
  return (
    field.supported &&
    field.editable &&
    ["text", "textarea", "number", "dropdown", "checkbox"].includes(
      field.type,
    )
  );
}

export function isDirectlyEditableField(
  field: PdfField,
): field is PdfField & { type: AgentFieldType | "radio" } {
  return (
    field.supported &&
    field.editable &&
    [
      "text",
      "textarea",
      "number",
      "dropdown",
      "checkbox",
      "radio",
    ].includes(field.type)
  );
}

export function getInitialFieldValue(field: PdfField): FieldValue {
  const fallbackValue = field.type === "checkbox" ? false : "";
  const value = field.value ?? fallbackValue;
  if (
    field.type === "dropdown" &&
    typeof value === "string" &&
    isPlaceholderDropdownOption(value)
  ) {
    return "";
  }
  return value;
}

export function hasInitialConfirmedValue(field: PdfField): boolean {
  if (!isDirectlyEditableField(field) || field.value === undefined) {
    return false;
  }

  if (field.type === "checkbox") {
    return field.value === true;
  }

  return isEditableValueCompatible(field, field.value);
}

export function isManuallyConfirmedValue(
  field: PdfField,
  value: FieldValue,
): boolean {
  return (
    isDirectlyEditableField(field) &&
    isEditableValueCompatible(field, value)
  );
}

function isEditableValueCompatible(
  field: PdfField & { type: AgentFieldType | "radio" },
  value: FieldValue,
): boolean {
  if (field.type === "radio") {
    return (
      typeof value === "string" &&
      Boolean(value.trim()) &&
      (field.options ?? []).includes(value)
    );
  }

  return isAgentValueCompatible(
    { type: field.type as AgentFieldType, options: field.options },
    value,
  );
}

export function getReviewFieldStatus(
  fieldId: string,
  proposedFieldId: string | null,
  confirmedFieldIds: Set<string>,
  skippedFieldIds: Set<string>,
): ReviewFieldStatus {
  if (fieldId === proposedFieldId) {
    return "proposed";
  }
  if (confirmedFieldIds.has(fieldId)) {
    return "confirmed";
  }
  if (skippedFieldIds.has(fieldId)) {
    return "skipped";
  }
  return "unanswered";
}

export function countReviewStatuses(
  items: Array<{ status: ReviewFieldStatus }>,
): Record<ReviewFieldStatus, number> {
  const counts: Record<ReviewFieldStatus, number> = {
    confirmed: 0,
    proposed: 0,
    skipped: 0,
    unanswered: 0,
  };
  for (const item of items) {
    counts[item.status] += 1;
  }
  return counts;
}

export function getReviewStatusLabel(status: ReviewFieldStatus): string {
  return status === "confirmed"
    ? "Completed"
    : status.charAt(0).toUpperCase() + status.slice(1);
}

export function formatReviewValue(value: FieldValue | undefined): string {
  if (value === true) {
    return "Yes";
  }
  if (value === false) {
    return "No";
  }
  return value?.trim() || "No reviewed answer";
}

export function buildAgentRequestFields(
  fields: PdfField[],
  values: Record<string, FieldValue>,
  confirmedFieldIds: Set<string>,
  skippedFieldIds: Set<string>,
): AgentRequestField[] {
  return fields
    .filter(isExplainableField)
    .filter(
      (field) =>
        field.type !== "dropdown" ||
        getAvailableDropdownOptions(field.options).length > 0,
    )
    .map((field) => {
      const value = values[field.id];
      const availableOptions =
        field.type === "dropdown"
          ? getAvailableDropdownOptions(field.options)
          : field.options;
      const isConfirmed =
        confirmedFieldIds.has(field.id) &&
        value !== undefined &&
        isAgentValueCompatible(field, value);
      const status: AgentFieldStatus = isConfirmed
        ? "confirmed"
        : skippedFieldIds.has(field.id)
          ? "skipped"
          : "unanswered";
      const requestField: AgentRequestField = {
        id: field.id,
        label: field.label || humanizeFieldId(field.id),
        question: field.question || field.label || humanizeFieldId(field.id),
        type: field.type,
        status,
        ...(field.page ? { page: field.page } : {}),
        ...(availableOptions ? { options: availableOptions } : {}),
        ...(field.help_text ? { help_text: field.help_text } : {}),
        ...(field.section ? { section: field.section } : {}),
        ...(field.page_context ? { page_context: field.page_context } : {}),
      };

      if (status === "confirmed" && value !== undefined) {
        requestField.confirmed_value = value;
      }

      return requestField;
    });
}

export function isAgentValueCompatible(
  field: { type: AgentFieldType; options?: string[] },
  value: FieldValue,
): boolean {
  if (field.type === "checkbox") {
    return typeof value === "boolean";
  }

  if (typeof value !== "string" || !value.trim()) {
    return false;
  }

  if (field.type === "number") {
    return numberPattern.test(value) || groupedNumberPattern.test(value);
  }

  if (field.type === "dropdown") {
    return getAvailableDropdownOptions(field.options).includes(value);
  }

  return true;
}

export function getAvailableDropdownOptions(options?: string[]): string[] {
  return (options ?? []).filter(
    (option) => !isPlaceholderDropdownOption(option),
  );
}

export function getQuickAnswerOptions(
  field: PdfField | undefined,
): Array<{ label: string; message: string; value: string }> {
  if (!field || !isExplainableField(field)) {
    return [];
  }

  if (field.type === "checkbox") {
    return [
      { label: "Yes", message: "Yes", value: "true" },
      { label: "No", message: "No", value: "false" },
    ];
  }

  if (field.type === "dropdown") {
    return getAvailableDropdownOptions(field.options).map((option) => ({
      label: option,
      message: option,
      value: option,
    }));
  }

  return [];
}

function isPlaceholderDropdownOption(option: string): boolean {
  const normalizedOption = option
    .trim()
    .replace(/^[-–—_:.…\s]+|[-–—_:.…\s]+$/g, "");
  if (!normalizedOption) {
    return true;
  }
  return dropdownPlaceholderPattern.test(normalizedOption);
}

export function getQuestionStatusLabel(phase: ConversationPhase): string {
  const labels: Record<ConversationPhase, string> = {
    support_setup: "Before we begin",
    asking: "Ready to begin",
    awaiting_answer: "Your current question",
    awaiting_clarification: "Let's clarify this",
    awaiting_confirmation: "Review your answer",
    awaiting_replacement: "Preparing a correction",
    awaiting_replacement_confirmation: "Review your correction",
    field_confirmed: "Answer added",
    field_skipped: "Question skipped",
    form_complete: "Interview complete",
  };

  return labels[phase];
}

export function getLatestAssistantTurn(
  messages: ConversationMessage[],
): { id: number; message: string } | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "assistant") {
      return {
        id: messages[index].id,
        message: messages[index].content,
      };
    }
  }
  return null;
}

export function getWebSourceQualityLabel(
  quality: WebGuidanceCitation["source_quality"],
): string {
  return {
    issuing_organization: "Known issuing-organisation source",
    public_authority: "Public-authority source",
    general_web: "General web source",
  }[quality];
}

export function agentRequestNeedsExternalGuidance(
  request: AgentRequest,
): boolean {
  if (
    request.event.type !== "message" &&
    request.event.type !== "focus_field"
  ) {
    return false;
  }
  const message = request.event.content;
  return [
    /\bwhy\b/i,
    /\b(?:what|which)\s+(?:is|was|are|were)\s+(?:the\s+)?(?:purpose|reason)\b/i,
    /\b(?:purpose|reason)\s+(?:of|for)\b/i,
    /\b(?:is|are|was|were|am)\b.{0,80}\b(?:legally\s+required|required|mandatory|optional|allowed|eligible)\b/i,
    /\bmust\s+(?:i|we|this|that|the)\b/i,
    /\b(?:legal\s+(?:effect|rules?|obligation)|law|eligibility\s+requirements?|official\s+(?:instructions?|guidance|worksheet|form)|current\s+guidance|check\s+(?:the\s+)?(?:web|guidance)|search(?:\s+(?:the\s+)?web)?|sources?)\b/i,
    /\b(?:what|which|do|does|can|could)\b.{0,60}\binstructions?\b/i,
    /\bwhere\s+(?:can|could|do|would)\s+i\s+(?:find|locate|obtain|look\s+up)\b/i,
  ].some((pattern) => pattern.test(message));
}

export function createInitialConversationState(): ConversationState {
  return {
    phase: "support_setup",
    active_field_id: null,
    pending_proposal: null,
    remembered_candidates: [],
    support_setup_step: "needs",
  };
}

export function formatAgentValue(value: FieldValue): string {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return value;
}

export function groupFieldsByPage(fields: PdfField[]): PageFieldGroup[] {
  const groups: PageFieldGroup[] = [];

  fields.forEach((field, index) => {
    const page = field.page ?? null;
    const currentGroup = groups[groups.length - 1];
    if (!currentGroup || currentGroup.page !== page) {
      groups.push({ page, fields: [{ field, index }] });
      return;
    }
    currentGroup.fields.push({ field, index });
  });

  return groups;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
