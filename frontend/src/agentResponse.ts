import { isAgentValueCompatible } from "./formFieldState";
import type {
  AgentEffect,
  AgentEffectKind,
  AgentRequestField,
  AgentResponse,
  AssistanceNeed,
  AssistancePreferences,
  ConversationPhase,
  ConversationState,
  OfficialGuidanceCitation,
  PendingProposal,
  WebGuidanceCitation,
  WebGuidanceMetadata,
} from "./formTypes";

export function parseAgentResponse(
  payload: unknown,
  requestFields: AgentRequestField[],
  requestState: ConversationState,
): AgentResponse {
  if (!isRecord(payload)) {
    throw new Error("The API returned an invalid form assistant response.");
  }

  if (
    typeof payload.assistant_message !== "string" ||
    !payload.assistant_message.trim()
  ) {
    throw new Error("The API returned an invalid form assistant response.");
  }
  const effect = parseAgentEffect(payload.effect, requestFields);
  const conversationState = parseConversationState(
    payload.conversation_state,
    requestFields,
  );
  const guidance = parseOfficialGuidance(payload.guidance);
  const webGuidance = parseWebGuidance(payload.web_guidance);
  validateAgentResponseState(
    effect,
    conversationState,
    requestFields,
    requestState,
  );
  return {
    assistant_message: payload.assistant_message.trim(),
    effect,
    conversation_state: conversationState,
    guidance,
    web_guidance: webGuidance,
  };
}

function parseOfficialGuidance(
  payload: unknown,
): OfficialGuidanceCitation[] {
  if (payload === undefined) {
    return [];
  }
  if (!Array.isArray(payload) || payload.length > 2) {
    throw new Error("The API returned invalid official guidance.");
  }

  return payload.map((citation) => {
    if (
      !isRecord(citation) ||
      typeof citation.source_id !== "string" ||
      typeof citation.title !== "string" ||
      typeof citation.organization !== "string" ||
      typeof citation.url !== "string" ||
      !citation.url.startsWith("https://") ||
      typeof citation.form_version !== "string" ||
      typeof citation.retrieved_at !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(citation.retrieved_at) ||
      typeof citation.excerpt !== "string" ||
      citation.excerpt_kind !== "paraphrase"
    ) {
      throw new Error("The API returned invalid official guidance.");
    }
    return {
      source_id: citation.source_id,
      title: citation.title,
      organization: citation.organization,
      url: citation.url,
      form_version: citation.form_version,
      retrieved_at: citation.retrieved_at,
      excerpt: citation.excerpt,
      excerpt_kind: citation.excerpt_kind,
    };
  });
}

function parseWebGuidance(payload: unknown): WebGuidanceMetadata | null {
  if (payload === undefined || payload === null) {
    return null;
  }
  if (
    !isRecord(payload) ||
    payload.provider !== "tavily" ||
    ![
      "used",
      "limited",
      "conflicting",
      "empty",
      "unavailable",
    ].includes(String(payload.status)) ||
    !["meaning", "purpose", "requirements", "where_to_find"].includes(
      String(payload.topic),
    ) ||
    typeof payload.notice !== "string" ||
    !payload.notice.trim() ||
    !Array.isArray(payload.sources) ||
    payload.sources.length > 3
  ) {
    throw new Error("The API returned invalid live web guidance.");
  }

  const sources = payload.sources.map((source) => {
    if (
      !isRecord(source) ||
      typeof source.source_id !== "string" ||
      typeof source.title !== "string" ||
      typeof source.url !== "string" ||
      !source.url.startsWith("https://") ||
      typeof source.hostname !== "string" ||
      typeof source.retrieved_at !== "string" ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(
        source.retrieved_at,
      ) ||
      (source.form_version !== null &&
        source.form_version !== undefined &&
        typeof source.form_version !== "string") ||
      typeof source.snippet !== "string" ||
      ![
        "issuing_organization",
        "public_authority",
        "general_web",
      ].includes(String(source.source_quality))
    ) {
      throw new Error("The API returned invalid live web guidance.");
    }
    return source as WebGuidanceCitation;
  });

  const status = payload.status as WebGuidanceMetadata["status"];
  const hasNoSources = ["empty", "unavailable"].includes(status);
  if (
    (hasNoSources && sources.length > 0) ||
    (!hasNoSources && sources.length === 0)
  ) {
    throw new Error("The API returned invalid live web guidance.");
  }
  return {
    provider: "tavily",
    status,
    topic: payload.topic as WebGuidanceMetadata["topic"],
    notice: payload.notice,
    sources,
  };
}

function parseAgentEffect(
  payload: unknown,
  requestFields: AgentRequestField[],
): AgentEffect {
  if (!isRecord(payload) || !isAgentEffectKind(payload.effect)) {
    throw new Error("The API returned an invalid form assistant response.");
  }

  if (payload.effect === "completed") {
    return { effect: "completed" };
  }

  const fieldId = payload.field_id;
  if (payload.effect === "assistance_preferences_updated") {
    if (
      fieldId !== null &&
      (typeof fieldId !== "string" || !findAgentField(requestFields, fieldId))
    ) {
      throw new Error("The form assistant returned an invalid support update.");
    }
    if (!isSupportIntroductionStatus(payload.introduction_status)) {
      throw new Error("The form assistant returned an invalid support update.");
    }
    return {
      effect: "assistance_preferences_updated",
      preferences: parseAssistancePreferences(payload.preferences),
      introduction_status: payload.introduction_status,
      field_id: fieldId,
    };
  }

  if (payload.effect === "none") {
    if (fieldId !== null && typeof fieldId !== "string") {
      throw new Error("The API returned an invalid form assistant response.");
    }
    if (typeof fieldId === "string" && !findAgentField(requestFields, fieldId)) {
      throw new Error("The form assistant returned an unknown field.");
    }
    return { effect: "none", field_id: fieldId };
  }

  if (typeof fieldId !== "string") {
    throw new Error("The API returned an invalid form assistant response.");
  }

  const field = findAgentField(requestFields, fieldId);
  if (!field) {
    throw new Error("The form assistant returned an unknown field.");
  }

  if (
    payload.effect === "proposal" ||
    payload.effect === "replacement_proposal"
  ) {
    const originalValue = payload.original_value;
    const preparedValue = payload.prepared_value;
    const transformation = payload.transformation;
    if (
      (typeof originalValue !== "string" &&
        typeof originalValue !== "boolean") ||
      (typeof preparedValue !== "string" &&
        typeof preparedValue !== "boolean") ||
      !isAgentValueCompatible(field, preparedValue) ||
      (transformation !== null && typeof transformation !== "string")
    ) {
      throw new Error("The form assistant returned an invalid proposal.");
    }
    if (payload.effect === "replacement_proposal") {
      const previousConfirmedValue = payload.previous_confirmed_value;
      if (
        field.status !== "confirmed" ||
        (typeof previousConfirmedValue !== "string" &&
          typeof previousConfirmedValue !== "boolean") ||
        previousConfirmedValue !== field.confirmed_value
      ) {
        throw new Error(
          "The form assistant returned an invalid replacement proposal.",
        );
      }
      return {
        effect: "replacement_proposal",
        field_id: fieldId,
        previous_confirmed_value: previousConfirmedValue,
        original_value: originalValue,
        prepared_value: preparedValue,
        transformation,
      };
    }
    return {
      effect: "proposal",
      field_id: fieldId,
      original_value: originalValue,
      prepared_value: preparedValue,
      transformation,
    };
  }

  if (payload.effect === "confirmed") {
    const value = payload.value;
    if (
      (typeof value !== "string" && typeof value !== "boolean") ||
      !isAgentValueCompatible(field, value)
    ) {
      throw new Error("The form assistant returned an invalid proposal.");
    }
    return { effect: "confirmed", field_id: fieldId, value };
  }

  return { effect: payload.effect, field_id: fieldId };
}

function parseConversationState(
  payload: unknown,
  requestFields: AgentRequestField[],
): ConversationState {
  if (
    !isRecord(payload) ||
    !isConversationPhase(payload.phase) ||
    (payload.active_field_id !== null &&
      typeof payload.active_field_id !== "string")
  ) {
    throw new Error("The API returned an invalid conversation state.");
  }

  const activeFieldId = payload.active_field_id;
  const supportSetupStep = payload.support_setup_step ?? null;
  if (
    supportSetupStep !== null &&
    !["needs", "needs_after_interaction", "interaction"].includes(
      String(supportSetupStep),
    )
  ) {
    throw new Error("The API returned an invalid support setup state.");
  }
  if (
    typeof activeFieldId === "string" &&
    !findAgentField(requestFields, activeFieldId)
  ) {
    throw new Error("The conversation state referenced an unknown field.");
  }

  let pendingProposal: PendingProposal | null = null;
  if (payload.pending_proposal !== null) {
    if (!isRecord(payload.pending_proposal)) {
      throw new Error("The API returned an invalid pending proposal.");
    }
    const pendingFieldId = payload.pending_proposal.field_id;
    const pendingValue = payload.pending_proposal.value;
    const pendingField =
      typeof pendingFieldId === "string"
        ? findAgentField(requestFields, pendingFieldId)
        : undefined;
    if (
      !pendingField ||
      (typeof pendingValue !== "string" &&
        typeof pendingValue !== "boolean") ||
      !isAgentValueCompatible(pendingField, pendingValue)
    ) {
      throw new Error("The API returned an invalid pending proposal.");
    }
    if (payload.pending_proposal.operation === "replacement") {
      const previousConfirmedValue =
        payload.pending_proposal.previous_confirmed_value;
      if (
        pendingField.status !== "confirmed" ||
        (typeof previousConfirmedValue !== "string" &&
          typeof previousConfirmedValue !== "boolean") ||
        previousConfirmedValue !== pendingField.confirmed_value
      ) {
        throw new Error("The API returned an invalid pending replacement.");
      }
      pendingProposal = {
        operation: "replacement",
        field_id: pendingField.id,
        previous_confirmed_value: previousConfirmedValue,
        value: pendingValue,
      };
    } else {
      if (payload.pending_proposal.operation !== undefined) {
        throw new Error("The API returned an invalid pending proposal.");
      }
      pendingProposal = { field_id: pendingField.id, value: pendingValue };
    }
  }

  const rememberedPayload = payload.remembered_candidates ?? [];
  if (!Array.isArray(rememberedPayload) || rememberedPayload.length > 5) {
    throw new Error("The API returned invalid remembered answers.");
  }
  const rememberedFieldIds = new Set<string>();
  const rememberedCandidates = rememberedPayload.map((candidate) => {
    if (!isRecord(candidate)) {
      throw new Error("The API returned an invalid remembered answer.");
    }
    const fieldId = candidate.field_id;
    const originalValue = candidate.original_value;
    const value = candidate.value;
    const field =
      typeof fieldId === "string"
        ? findAgentField(requestFields, fieldId)
        : undefined;
    if (
      !field ||
      field.status !== "unanswered" ||
      rememberedFieldIds.has(field.id) ||
      (typeof originalValue !== "string" &&
        typeof originalValue !== "boolean") ||
      (typeof value !== "string" && typeof value !== "boolean") ||
      !isAgentValueCompatible(field, value)
    ) {
      throw new Error("The API returned an invalid remembered answer.");
    }
    rememberedFieldIds.add(field.id);
    return {
      field_id: field.id,
      original_value: originalValue,
      value,
    };
  });

  const state: ConversationState = {
    phase: payload.phase,
    active_field_id: activeFieldId,
    pending_proposal: pendingProposal,
    remembered_candidates: rememberedCandidates,
    support_setup_step: supportSetupStep as
      | "needs"
      | "needs_after_interaction"
      | "interaction"
      | null,
  };
  const phaseNeedsActiveField = [
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
    "awaiting_replacement",
    "awaiting_replacement_confirmation",
    "field_confirmed",
    "field_skipped",
  ].includes(state.phase);
  if (
    (phaseNeedsActiveField && state.active_field_id === null) ||
    (["support_setup", "asking", "form_complete"].includes(state.phase) &&
      state.active_field_id !== null) ||
    (state.phase === "support_setup" && state.support_setup_step === null) ||
    (state.phase !== "support_setup" && state.support_setup_step !== null) ||
    (["awaiting_confirmation", "awaiting_replacement_confirmation"].includes(
      state.phase,
    ) &&
      (state.pending_proposal === null ||
        state.pending_proposal.field_id !== state.active_field_id)) ||
    (state.phase === "awaiting_confirmation" &&
      state.pending_proposal !== null &&
      "operation" in state.pending_proposal) ||
    (state.phase === "awaiting_replacement_confirmation" &&
      (state.pending_proposal === null ||
        !("operation" in state.pending_proposal))) ||
    (!["awaiting_confirmation", "awaiting_replacement_confirmation"].includes(
      state.phase,
    ) &&
      state.pending_proposal !== null)
  ) {
    throw new Error("The API returned an invalid conversation state.");
  }
  return state;
}

function validateAgentResponseState(
  effect: AgentEffect,
  state: ConversationState,
  requestFields: AgentRequestField[],
  requestState: ConversationState,
) {
  const effectFieldId = "field_id" in effect ? effect.field_id : null;
  const effectField =
    effectFieldId === null
      ? undefined
      : findAgentField(requestFields, effectFieldId);
  const isInitialResolution =
    (effect.effect === "confirmed" &&
      requestState.phase === "awaiting_confirmation" &&
      effectField?.status === "unanswered") ||
    (effect.effect === "skipped" && effectField?.status === "unanswered");
  const isReplacementResolution =
    effect.effect === "confirmed" &&
    requestState.phase === "awaiting_replacement_confirmation" &&
    effectField?.status === "confirmed";
  const isResolutionEffect =
    isInitialResolution || isReplacementResolution;
  const expectedNextField = requestFields.find(
    (field) =>
      field.status === "unanswered" &&
      (!isInitialResolution || field.id !== effectFieldId),
  );
  const progressedToNextField =
    isResolutionEffect &&
    expectedNextField !== undefined &&
    state.phase === "awaiting_answer" &&
    state.active_field_id === expectedNextField.id;
  const completedForm =
    isResolutionEffect &&
    expectedNextField === undefined &&
    state.phase === "form_complete" &&
    state.active_field_id === null;
  const correctionCancelled =
    effect.effect === "correction_cancelled" &&
    ["awaiting_replacement", "awaiting_replacement_confirmation"].includes(
      requestState.phase,
    ) &&
    ((expectedNextField !== undefined &&
      state.phase === "awaiting_answer" &&
      state.active_field_id === expectedNextField.id) ||
      (expectedNextField === undefined &&
        state.phase === "form_complete" &&
        state.active_field_id === null));
  const replacementRejected =
    effect.effect === "rejected" &&
    requestState.phase === "awaiting_replacement_confirmation" &&
    effectField?.status === "confirmed" &&
    ((expectedNextField !== undefined &&
      state.phase === "awaiting_answer" &&
      state.active_field_id === expectedNextField.id) ||
      (expectedNextField === undefined &&
        state.phase === "form_complete" &&
        state.active_field_id === null));
  const isAssistanceUpdate =
    effect.effect === "assistance_preferences_updated";
  const validAssistanceUpdate =
    effect.effect === "assistance_preferences_updated" &&
    ((requestState.phase === "support_setup" &&
      effect.introduction_status === "pending" &&
      effect.field_id === null &&
      state.phase === "support_setup" &&
      state.active_field_id === null) ||
      (requestState.phase === "support_setup" &&
        effect.introduction_status !== "pending" &&
        ((expectedNextField !== undefined &&
          effect.field_id === expectedNextField.id &&
          state.phase === "awaiting_answer" &&
          state.active_field_id === expectedNextField.id) ||
          (expectedNextField === undefined &&
            effect.field_id === null &&
            state.phase === "form_complete" &&
            state.active_field_id === null))) ||
      (requestState.phase !== "support_setup" &&
        effect.introduction_status === "saved" &&
        effect.field_id === requestState.active_field_id &&
        state.phase === requestState.phase &&
        state.active_field_id === requestState.active_field_id &&
        JSON.stringify(state.pending_proposal) ===
          JSON.stringify(requestState.pending_proposal)));

  if (
    !isResolutionEffect &&
    !isAssistanceUpdate &&
    effect.effect !== "completed" &&
    effect.effect !== "correction_cancelled" &&
    !replacementRejected &&
    effectFieldId !== state.active_field_id
  ) {
    throw new Error("The assistant response and conversation state disagree.");
  }

  const validPhase =
    (effect.effect === "proposal" &&
      effectField?.status === "unanswered" &&
      state.phase === "awaiting_confirmation" &&
      state.pending_proposal?.field_id === effect.field_id &&
      !("operation" in state.pending_proposal) &&
      state.pending_proposal.value === effect.prepared_value) ||
    (effect.effect === "replacement_proposal" &&
      effectField?.status === "confirmed" &&
      state.phase === "awaiting_replacement_confirmation" &&
      state.pending_proposal?.field_id === effect.field_id &&
      "operation" in state.pending_proposal &&
      state.pending_proposal.previous_confirmed_value ===
        effect.previous_confirmed_value &&
      state.pending_proposal.value === effect.prepared_value) ||
    (effect.effect === "confirmed" &&
      (progressedToNextField || completedForm)) ||
    (effect.effect === "rejected" &&
      (state.phase === "awaiting_answer" || replacementRejected)) ||
    (effect.effect === "replacement_rejected" &&
      effectField?.status === "confirmed" &&
      state.phase === "awaiting_replacement") ||
    (effect.effect === "skipped" &&
      (progressedToNextField || completedForm)) ||
    validAssistanceUpdate ||
    (effect.effect === "none" &&
      [
        "support_setup",
        "asking",
        "awaiting_answer",
        "awaiting_clarification",
        "awaiting_confirmation",
        "awaiting_replacement",
        "awaiting_replacement_confirmation",
        "form_complete",
      ].includes(state.phase)) ||
    (effect.effect === "field_selected" &&
      effectField?.status === "unanswered" &&
      state.phase === "awaiting_answer") ||
    (effect.effect === "field_reopened" &&
      effectField?.status === "skipped" &&
      state.phase === "awaiting_answer") ||
    (effect.effect === "correction_started" &&
      effectField?.status === "confirmed" &&
      state.phase === "awaiting_replacement") ||
    correctionCancelled ||
    (effect.effect === "completed" && state.phase === "form_complete");
  if (!validPhase) {
    throw new Error("The assistant returned an invalid state transition.");
  }
}

function parseAssistancePreferences(payload: unknown): AssistancePreferences {
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.support_needs) ||
    payload.support_needs.length > 6 ||
    !["no_preference", "voice", "typing"].includes(
      String(payload.interaction_mode),
    ) ||
    payload.assistance_language !== "en" ||
    (payload.other_note !== null &&
      (typeof payload.other_note !== "string" ||
        !payload.other_note.trim() ||
        payload.other_note.length > 200))
  ) {
    throw new Error("The form assistant returned invalid support preferences.");
  }

  const allowedNeeds = new Set<AssistanceNeed>([
    "plain_language",
    "slower_pace",
    "organise_details",
    "reassurance",
    "explain_bureaucracy",
    "other",
  ]);
  const supportNeeds: AssistanceNeed[] = [];
  for (const need of payload.support_needs) {
    if (
      typeof need !== "string" ||
      !allowedNeeds.has(need as AssistanceNeed) ||
      supportNeeds.includes(need as AssistanceNeed)
    ) {
      throw new Error("The form assistant returned invalid support preferences.");
    }
    supportNeeds.push(need as AssistanceNeed);
  }

  if (
    supportNeeds.includes("other") !==
    (typeof payload.other_note === "string")
  ) {
    throw new Error("The form assistant returned invalid support preferences.");
  }

  return {
    support_needs: supportNeeds,
    interaction_mode:
      payload.interaction_mode as AssistancePreferences["interaction_mode"],
    other_note: payload.other_note as string | null,
    assistance_language: "en",
  };
}

function isSupportIntroductionStatus(
  value: unknown,
): value is "pending" | "saved" | "skipped" {
  return ["pending", "saved", "skipped"].includes(String(value));
}

function findAgentField(
  fields: AgentRequestField[],
  fieldId: string,
): AgentRequestField | undefined {
  return fields.find((field) => field.id === fieldId);
}

function isAgentEffectKind(value: unknown): value is AgentEffectKind {
  return [
    "none",
    "assistance_preferences_updated",
    "proposal",
    "replacement_proposal",
    "confirmed",
    "rejected",
    "skipped",
    "field_selected",
    "field_reopened",
    "correction_started",
    "replacement_rejected",
    "correction_cancelled",
    "completed",
  ].includes(value as AgentEffectKind);
}

function isConversationPhase(value: unknown): value is ConversationPhase {
  return [
    "support_setup",
    "asking",
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
    "awaiting_replacement",
    "awaiting_replacement_confirmation",
    "field_confirmed",
    "field_skipped",
    "form_complete",
  ].includes(value as ConversationPhase);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
