export type ConnectionStatus = "checking" | "connected" | "disconnected";
export type ExtractionStatus = "idle" | "loading" | "ready" | "empty" | "error";
export type PreviewStatus = "idle" | "pending" | "updating" | "ready" | "error";
export type AgentStatus = "idle" | "loading" | "error";
export type AgentActivity = "responding" | "guidance";
export type MobileWorkspaceView = "assistant" | "form";
export type FieldValue = string | boolean;
export type AssistanceNeed =
  | "plain_language"
  | "slower_pace"
  | "organise_details"
  | "reassurance"
  | "explain_bureaucracy"
  | "other";
export type InteractionModePreference =
  | "no_preference"
  | "voice"
  | "typing";
export type SupportIntroductionStatus = "pending" | "saved" | "skipped";

export type AssistancePreferences = {
  support_needs: AssistanceNeed[];
  interaction_mode: InteractionModePreference;
  other_note: string | null;
  assistance_language: "en";
};

export type AgentEffectKind =
  | "none"
  | "assistance_preferences_updated"
  | "proposal"
  | "replacement_proposal"
  | "confirmed"
  | "rejected"
  | "skipped"
  | "field_selected"
  | "field_reopened"
  | "correction_started"
  | "replacement_rejected"
  | "correction_cancelled"
  | "completed";

export type AgentFieldStatus = "unanswered" | "confirmed" | "skipped";
export type ReviewFieldStatus =
  | "unanswered"
  | "confirmed"
  | "skipped"
  | "proposed";

export type ConversationPhase =
  | "support_setup"
  | "asking"
  | "awaiting_answer"
  | "awaiting_clarification"
  | "awaiting_confirmation"
  | "awaiting_replacement"
  | "awaiting_replacement_confirmation"
  | "field_confirmed"
  | "field_skipped"
  | "form_complete";

export type AgentFieldType =
  | "text"
  | "textarea"
  | "number"
  | "dropdown"
  | "checkbox";

export type HealthResponse = {
  status: string;
  service: string;
};

export type PdfWidgetGeometry = {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type PdfField = {
  id: string;
  label: string;
  type: string;
  question?: string;
  supported: boolean;
  editable: boolean;
  page?: number;
  options?: string[];
  value?: FieldValue;
  capability_reason?: string;
  help_text?: string;
  section?: string;
  page_context?: string;
  widgets?: PdfWidgetGeometry[];
};

export type PageFieldGroup = {
  page: number | null;
  fields: Array<{ field: PdfField; index: number }>;
};

export type FormContext = {
  title?: string | null;
  instructions: string[];
  form_id?: string | null;
  form_version?: string | null;
};

export type PdfExtractionResponse = {
  fields: PdfField[];
  form_context: FormContext;
};

export type OfficialGuidanceCitation = {
  source_id: string;
  title: string;
  organization: string;
  url: string;
  form_version: string;
  retrieved_at: string;
  excerpt: string;
  excerpt_kind: "paraphrase";
};

export type WebGuidanceCitation = {
  source_id: string;
  title: string;
  url: string;
  hostname: string;
  retrieved_at: string;
  form_version?: string | null;
  snippet: string;
  source_quality:
    | "issuing_organization"
    | "public_authority"
    | "general_web";
};

export type WebGuidanceMetadata = {
  provider: "tavily";
  status:
    | "used"
    | "limited"
    | "conflicting"
    | "empty"
    | "unavailable";
  topic: "meaning" | "purpose" | "requirements" | "where_to_find";
  notice: string;
  sources: WebGuidanceCitation[];
};

export type AgentRequestField = {
  id: string;
  label: string;
  question?: string;
  help_text?: string;
  section?: string;
  page_context?: string;
  type: AgentFieldType;
  page?: number;
  options?: string[];
  status: AgentFieldStatus;
  confirmed_value?: FieldValue;
};

export type AgentHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type PendingProposal =
  | {
      field_id: string;
      value: FieldValue;
    }
  | {
      operation: "replacement";
      field_id: string;
      previous_confirmed_value: FieldValue;
      value: FieldValue;
    };

export type RememberedCandidate = {
  field_id: string;
  original_value: FieldValue;
  value: FieldValue;
};

export type ConversationState = {
  phase: ConversationPhase;
  active_field_id: string | null;
  pending_proposal: PendingProposal | null;
  remembered_candidates: RememberedCandidate[];
  support_setup_step?:
    | "needs"
    | "needs_after_interaction"
    | "interaction"
    | null;
};

export type AgentEvent =
  | { type: "advance" }
  | { type: "message"; content: string }
  | { type: "focus_field"; field_id: string; content: string }
  | { type: "confirm" }
  | { type: "confirm_edit"; value: FieldValue }
  | { type: "reject" }
  | { type: "cancel_correction" }
  | { type: "skip"; field_id: string };

export type AgentRequest = {
  form_context: FormContext;
  fields: AgentRequestField[];
  conversation_state: ConversationState;
  event: AgentEvent;
  assistance_preferences: AssistancePreferences;
  history: AgentHistoryMessage[];
};

export type AgentEffect =
  | {
      effect: "none";
      field_id: string | null;
    }
  | {
      effect: "assistance_preferences_updated";
      preferences: AssistancePreferences;
      introduction_status: SupportIntroductionStatus;
      field_id: string | null;
    }
  | {
      effect: "proposal";
      field_id: string;
      original_value: FieldValue;
      prepared_value: FieldValue;
      transformation: string | null;
    }
  | {
      effect: "replacement_proposal";
      field_id: string;
      previous_confirmed_value: FieldValue;
      original_value: FieldValue;
      prepared_value: FieldValue;
      transformation: string | null;
    }
  | {
      effect: "confirmed";
      field_id: string;
      value: FieldValue;
    }
  | {
      effect:
        | "rejected"
        | "skipped"
        | "field_selected"
        | "field_reopened"
        | "correction_started"
        | "replacement_rejected"
        | "correction_cancelled";
      field_id: string;
    }
  | {
      effect: "completed";
    };

export type AgentResponse = {
  assistant_message: string;
  effect: AgentEffect;
  conversation_state: ConversationState;
  guidance: OfficialGuidanceCitation[];
  web_guidance: WebGuidanceMetadata | null;
};

export type ProposalAgentEffect =
  | Extract<AgentEffect, { effect: "proposal" }>
  | Extract<AgentEffect, { effect: "replacement_proposal" }>;

export type ConversationMessage = AgentHistoryMessage & {
  id: number;
  effect?: AgentEffect;
  fieldId?: string | null;
  guidance?: OfficialGuidanceCitation[];
  webGuidance?: WebGuidanceMetadata | null;
  webGuidanceRetry?: AgentRequest;
};

export type ReviewItem = {
  field: PdfField;
  status: ReviewFieldStatus;
};
