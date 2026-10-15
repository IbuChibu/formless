import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import PdfViewer from "./PdfViewer";
import VoiceAssistantPanel from "./VoiceAssistantPanel";
import useVoiceAssistant from "./useVoiceAssistant";
import useVoiceInterview from "./useVoiceInterview";

type ConnectionStatus = "checking" | "connected" | "disconnected";
type ExtractionStatus = "idle" | "loading" | "ready" | "empty" | "error";
type PreviewStatus = "idle" | "pending" | "updating" | "ready" | "error";
type AgentStatus = "idle" | "loading" | "error";
type AgentActivity = "responding" | "guidance";
type MobileWorkspaceView = "assistant" | "form";
type FieldValue = string | boolean;
type AgentEffectKind =
  | "none"
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
type AgentFieldStatus = "unanswered" | "confirmed" | "skipped";
type ConversationPhase =
  | "asking"
  | "awaiting_answer"
  | "awaiting_clarification"
  | "awaiting_confirmation"
  | "awaiting_replacement"
  | "awaiting_replacement_confirmation"
  | "field_confirmed"
  | "field_skipped"
  | "form_complete";
type AgentFieldType =
  | "text"
  | "textarea"
  | "number"
  | "dropdown"
  | "checkbox";

type HealthResponse = {
  status: string;
  service: string;
};

type PdfField = {
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
};

type PageFieldGroup = {
  page: number | null;
  fields: Array<{ field: PdfField; index: number }>;
};

type PdfExtractionResponse = {
  fields: PdfField[];
  form_context: FormContext;
};

type FormContext = {
  title?: string | null;
  instructions: string[];
  form_id?: string | null;
  form_version?: string | null;
};

type OfficialGuidanceCitation = {
  source_id: string;
  title: string;
  organization: string;
  url: string;
  form_version: string;
  retrieved_at: string;
  excerpt: string;
  excerpt_kind: "paraphrase";
};

type WebGuidanceCitation = {
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

type WebGuidanceMetadata = {
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

type AgentRequestField = {
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

type AgentHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type AgentRequest = {
  form_context: FormContext;
  fields: AgentRequestField[];
  conversation_state: ConversationState;
  event: AgentEvent;
  history: AgentHistoryMessage[];
};

type PendingProposal =
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

type RememberedCandidate = {
  field_id: string;
  original_value: FieldValue;
  value: FieldValue;
};

type ConversationState = {
  phase: ConversationPhase;
  active_field_id: string | null;
  pending_proposal: PendingProposal | null;
  remembered_candidates: RememberedCandidate[];
};

type AgentEvent =
  | { type: "advance" }
  | { type: "message"; content: string }
  | { type: "focus_field"; field_id: string; content: string }
  | { type: "confirm" }
  | { type: "confirm_edit"; value: FieldValue }
  | { type: "reject" }
  | { type: "cancel_correction" }
  | { type: "skip"; field_id: string };

type AgentEffect =
  | {
      effect: "none";
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

type AgentResponse = {
  assistant_message: string;
  effect: AgentEffect;
  conversation_state: ConversationState;
  guidance: OfficialGuidanceCitation[];
  web_guidance: WebGuidanceMetadata | null;
};

type ProposalAgentEffect =
  | Extract<AgentEffect, { effect: "proposal" }>
  | Extract<AgentEffect, { effect: "replacement_proposal" }>;

type ConversationMessage = AgentHistoryMessage & {
  id: number;
  effect?: AgentEffect;
  fieldId?: string | null;
  guidance?: OfficialGuidanceCitation[];
  webGuidance?: WebGuidanceMetadata | null;
  webGuidanceRetry?: AgentRequest;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const previewDebounceMs = 600;
const maxAgentHistoryMessages = 8;
const numberPattern = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;
const groupedNumberPattern = /^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?$/;
const dropdownPlaceholderPattern =
  /^(?:please\s+)?(?:select|choose)(?:\s+(?:one|an?\s+option))?$/i;

function App() {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("checking");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fields, setFields] = useState<PdfField[]>([]);
  const [formContext, setFormContext] = useState<FormContext>({
    instructions: [],
  });
  const [formValues, setFormValues] = useState<Record<string, FieldValue>>({});
  const [changedValues, setChangedValues] = useState<
    Record<string, FieldValue>
  >({});
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [extractionStatus, setExtractionStatus] =
    useState<ExtractionStatus>("idle");
  const [previewStatus, setPreviewStatus] =
    useState<PreviewStatus>("idle");
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [confirmedFieldIds, setConfirmedFieldIds] = useState<Set<string>>(
    new Set(),
  );
  const [skippedFieldIds, setSkippedFieldIds] = useState<Set<string>>(
    new Set(),
  );
  const [agentConversationState, setAgentConversationState] =
    useState<ConversationState>(createInitialConversationState());
  const [agentMessages, setAgentMessages] = useState<ConversationMessage[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>("idle");
  const [agentActivity, setAgentActivity] =
    useState<AgentActivity>("responding");
  const [agentInput, setAgentInput] = useState("");
  const [agentError, setAgentError] = useState<string | null>(null);
  const [failedAgentRequest, setFailedAgentRequest] =
    useState<AgentRequest | null>(null);
  const [isEditingProposal, setIsEditingProposal] = useState(false);
  const [proposalEditValue, setProposalEditValue] =
    useState<FieldValue>("");
  const [pendingProposalDetails, setPendingProposalDetails] =
    useState<ProposalAgentEffect | null>(null);
  const [manualDrawerOpen, setManualDrawerOpen] = useState(false);
  const [showFullTranscript, setShowFullTranscript] = useState(false);
  const [mobileWorkspaceView, setMobileWorkspaceView] =
    useState<MobileWorkspaceView>("assistant");
  const voice = useVoiceAssistant();

  const originalUrlRef = useRef<string | null>(null);
  const filledUrlRef = useRef<string | null>(null);
  const extractionControllerRef = useRef<AbortController | null>(null);
  const agentControllerRef = useRef<AbortController | null>(null);
  const agentRequestInFlightRef = useRef(false);
  const agentMessageIdRef = useRef(0);
  const agentInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function checkBackend() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
        });
        const health: HealthResponse = await response.json();

        if (!response.ok || health.status !== "ok") {
          throw new Error("Backend health check failed");
        }

        setConnectionStatus("connected");
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }

        setConnectionStatus("disconnected");
      }
    }

    void checkBackend();

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (
      !selectedFile ||
      extractionStatus !== "ready" ||
      Object.keys(changedValues).length === 0
    ) {
      return;
    }

    const fileToFill = selectedFile;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      async function refreshPreview() {
        setPreviewStatus("updating");
        setPreviewError(null);

        const formData = new FormData();
        formData.append("file", fileToFill);
        formData.append("values", JSON.stringify(changedValues));

        try {
          const response = await fetch(`${apiBaseUrl}/pdf/fill`, {
            method: "POST",
            body: formData,
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(await readApiError(response));
          }

          const filledPdf = await response.blob();
          if (controller.signal.aborted) {
            return;
          }

          const nextUrl = URL.createObjectURL(filledPdf);
          if (filledUrlRef.current) {
            URL.revokeObjectURL(filledUrlRef.current);
          }

          filledUrlRef.current = nextUrl;
          setPreviewUrl(nextUrl);
          setDownloadUrl(nextUrl);
          setPreviewStatus("ready");
        } catch (error) {
          if (isAbortError(error)) {
            return;
          }

          setPreviewError(getErrorMessage(error));
          setPreviewStatus("error");
        }
      }

      void refreshPreview();
    }, previewDebounceMs);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [changedValues, extractionStatus, selectedFile]);

  useEffect(() => {
    return () => {
      extractionControllerRef.current?.abort();
      agentControllerRef.current?.abort();
      if (originalUrlRef.current) {
        URL.revokeObjectURL(originalUrlRef.current);
      }
      if (filledUrlRef.current) {
        URL.revokeObjectURL(filledUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (
      agentStatus === "idle" &&
      [
        "awaiting_answer",
        "awaiting_clarification",
        "awaiting_replacement",
      ].includes(agentConversationState.phase)
    ) {
      agentInputRef.current?.focus();
    }
  }, [
    agentConversationState.active_field_id,
    agentConversationState.phase,
    agentStatus,
  ]);

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.type !== "application/pdf") {
      setExtractionError("Choose a PDF file to continue.");
      setExtractionStatus("error");
      return;
    }

    extractionControllerRef.current?.abort();
    agentControllerRef.current?.abort();
    agentControllerRef.current = null;
    agentRequestInFlightRef.current = false;
    const controller = new AbortController();
    extractionControllerRef.current = controller;

    if (originalUrlRef.current) {
      URL.revokeObjectURL(originalUrlRef.current);
    }
    if (filledUrlRef.current) {
      URL.revokeObjectURL(filledUrlRef.current);
      filledUrlRef.current = null;
    }

    const originalUrl = URL.createObjectURL(file);
    originalUrlRef.current = originalUrl;

    setSelectedFile(file);
    setPreviewUrl(originalUrl);
    setDownloadUrl(null);
    setFields([]);
    setFormContext({ instructions: [] });
    setFormValues({});
    setChangedValues({});
    setExtractionError(null);
    setPreviewError(null);
    setConfirmedFieldIds(new Set());
    setSkippedFieldIds(new Set());
    setAgentConversationState(createInitialConversationState());
    setAgentMessages([]);
    setAgentStatus("idle");
    setAgentActivity("responding");
    setAgentInput("");
    setAgentError(null);
    setFailedAgentRequest(null);
    setIsEditingProposal(false);
    setProposalEditValue("");
    setPendingProposalDetails(null);
    setManualDrawerOpen(false);
    setShowFullTranscript(false);
    setMobileWorkspaceView("assistant");
    voiceInterview.resetInterview();
    agentMessageIdRef.current = 0;
    setExtractionStatus("loading");
    setPreviewStatus("idle");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${apiBaseUrl}/pdf/extract`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const extraction = (await response.json()) as PdfExtractionResponse;
      if (
        !Array.isArray(extraction.fields) ||
        !isValidFormContext(extraction.form_context)
      ) {
        throw new Error("The API returned an invalid field response.");
      }

      const initialValues = Object.fromEntries(
        extraction.fields.map((field) => [
          field.id,
          getInitialFieldValue(field),
        ]),
      );

      setFields(extraction.fields);
      setFormContext(extraction.form_context);
      setFormValues(initialValues);
      setConfirmedFieldIds(
        new Set(
          extraction.fields
            .filter((field) => hasInitialConfirmedValue(field))
            .map((field) => field.id),
        ),
      );
      setExtractionStatus(extraction.fields.length > 0 ? "ready" : "empty");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      setExtractionError(getErrorMessage(error));
      setExtractionStatus("error");
    }
  }

  function updateField(fieldId: string, value: FieldValue) {
    const field = fields.find((candidate) => candidate.id === fieldId);
    if (!field || !field.supported || !field.editable) {
      return;
    }

    const isConfirmed = isManuallyConfirmedValue(field, value);

    writeFieldValue(fieldId, value, isConfirmed);

    if (
      agentConversationState.active_field_id === fieldId ||
      agentConversationState.pending_proposal?.field_id === fieldId
    ) {
      setAgentConversationState({
        phase: isConfirmed ? "field_confirmed" : "awaiting_answer",
        active_field_id: fieldId,
        pending_proposal: null,
        remembered_candidates:
          agentConversationState.remembered_candidates.filter(
            (candidate) => candidate.field_id !== fieldId,
          ),
      });
      resetProposalEditor();
    }
  }

  function writeFieldValue(
    fieldId: string,
    value: FieldValue,
    isConfirmed: boolean,
  ) {
    setFormValues((current) => ({ ...current, [fieldId]: value }));
    setChangedValues((current) => ({ ...current, [fieldId]: value }));
    setConfirmedFieldIds((current) => {
      const next = new Set(current);
      if (isConfirmed) {
        next.add(fieldId);
      } else {
        next.delete(fieldId);
      }
      return next;
    });
    setSkippedFieldIds((current) => {
      const next = new Set(current);
      next.delete(fieldId);
      return next;
    });
    setPreviewError(null);
    setPreviewStatus("pending");
  }

  function resetProposalEditor() {
    setIsEditingProposal(false);
    setProposalEditValue("");
    setPendingProposalDetails(null);
  }

  function confirmPendingProposal(value: FieldValue) {
    const pendingProposal = agentConversationState.pending_proposal;
    if (!pendingProposal) {
      return;
    }

    const field = fields.find(
      (candidate) => candidate.id === pendingProposal.field_id,
    );
    if (
      !field ||
      !isExplainableField(field) ||
      !isAgentValueCompatible(field, value)
    ) {
      setAgentError(
        "This proposal no longer matches the extracted form field.",
      );
      setAgentStatus("error");
      return;
    }

    sendAgentEvent(
      value === pendingProposal.value
        ? { type: "confirm" }
        : { type: "confirm_edit", value },
    );
  }

  function rejectPendingProposal() {
    if (!agentConversationState.pending_proposal) {
      return;
    }
    sendAgentEvent({ type: "reject" });
  }

  function useOriginalProposal() {
    if (!pendingProposalDetails) {
      return;
    }
    confirmPendingProposal(pendingProposalDetails.original_value);
  }

  function skipPendingProposal() {
    if (!agentConversationState.pending_proposal) {
      return;
    }
    sendAgentEvent({
      type: "skip",
      field_id: agentConversationState.pending_proposal.field_id,
    });
  }

  function appendAgentMessage(message: Omit<ConversationMessage, "id">) {
    agentMessageIdRef.current += 1;
    const nextMessage = { ...message, id: agentMessageIdRef.current };
    setAgentMessages((current) => [...current, nextMessage]);
  }

  async function requestAgent(request: AgentRequest) {
    if (agentRequestInFlightRef.current) {
      return;
    }

    agentRequestInFlightRef.current = true;
    const controller = new AbortController();
    agentControllerRef.current = controller;
    setAgentStatus("loading");
    setAgentActivity(
      agentRequestNeedsExternalGuidance(request) ? "guidance" : "responding",
    );
    setAgentError(null);
    setFailedAgentRequest(null);

    try {
      const response = await fetch(`${apiBaseUrl}/agent/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const agentResponse = parseAgentResponse(
        await response.json(),
        request.fields,
        request.conversation_state,
      );
      const {
        assistant_message: assistantMessage,
        effect,
        conversation_state: conversationState,
      } = agentResponse;

      if (controller.signal.aborted) {
        return;
      }

      appendAgentMessage({
        role: "assistant",
        content: assistantMessage,
        effect,
        fieldId: "field_id" in effect ? effect.field_id : null,
        guidance: agentResponse.guidance,
        webGuidance: agentResponse.web_guidance,
        ...(["empty", "unavailable"].includes(
          agentResponse.web_guidance?.status ?? "",
        )
          ? { webGuidanceRetry: request }
          : {}),
      });
      setAgentConversationState(conversationState);

      if (
        effect.effect === "proposal" ||
        effect.effect === "replacement_proposal"
      ) {
        setProposalEditValue(effect.prepared_value);
        setPendingProposalDetails(effect);
        setIsEditingProposal(false);
      } else if (effect.effect === "confirmed") {
        writeFieldValue(effect.field_id, effect.value, true);
        resetProposalEditor();
      } else if (effect.effect === "skipped") {
        const skippedField = request.fields.find(
          (field) => field.id === effect.field_id,
        );
        if (skippedField?.status === "unanswered") {
          setSkippedFieldIds((current) =>
            new Set(current).add(effect.field_id),
          );
        }
        setConfirmedFieldIds((current) => {
          const next = new Set(current);
          next.delete(effect.field_id);
          return next;
        });
        resetProposalEditor();
      } else if (effect.effect === "field_reopened") {
        setSkippedFieldIds((current) => {
          const next = new Set(current);
          next.delete(effect.field_id);
          return next;
        });
        resetProposalEditor();
      } else if (
        ![
          "awaiting_confirmation",
          "awaiting_replacement_confirmation",
        ].includes(conversationState.phase)
      ) {
        resetProposalEditor();
      }
      setAgentStatus("idle");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      setAgentError(getErrorMessage(error));
      setFailedAgentRequest(request);
      setAgentStatus("error");
    } finally {
      if (agentControllerRef.current === controller) {
        agentControllerRef.current = null;
        agentRequestInFlightRef.current = false;
      }
    }
  }

  function sendAgentEvent(event: AgentEvent, visibleMessage?: string) {
    if (agentStatus === "loading" || agentRequestInFlightRef.current) {
      return;
    }

    const requestFields = buildAgentRequestFields(
      fields,
      formValues,
      confirmedFieldIds,
      skippedFieldIds,
    );
    if (requestFields.length === 0) {
      setAgentError(
        "This form does not contain fields the assistant supports.",
      );
      setAgentStatus("error");
      return;
    }

    const request: AgentRequest = {
      form_context: formContext,
      fields: requestFields,
      conversation_state: agentConversationState,
      event,
      history: agentMessages
        .slice(-maxAgentHistoryMessages)
        .map(({ role, content }) => ({ role, content })),
    };

    if (visibleMessage) {
      appendAgentMessage({ role: "user", content: visibleMessage });
    }
    setAgentInput("");
    void requestAgent(request);
  }

  function sendAgentMessage(message: string) {
    const normalizedMessage = message.trim();
    if (!normalizedMessage) {
      return;
    }
    sendAgentEvent(
      { type: "message", content: normalizedMessage },
      normalizedMessage,
    );
  }

  function submitAgentMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendAgentMessage(agentInput);
  }

  const connectionCopy = {
    checking: "Checking backend",
    connected: "Backend connected",
    disconnected: "Backend unavailable",
  }[connectionStatus];

  const previewCopy = {
    idle: "Original document",
    pending: "Changes pending",
    updating: "Updating preview",
    ready: "Preview up to date",
    error: "Preview update failed",
  }[previewStatus];

  const completedFilename = selectedFile
    ? `completed-${selectedFile.name}`
    : "completed-form.pdf";
  const fieldGroups = groupFieldsByPage(fields);
  const agentActiveFieldId = agentConversationState.active_field_id;
  const pendingProposal = agentConversationState.pending_proposal;
  const isReplacementPending = Boolean(
    pendingProposal &&
      "operation" in pendingProposal &&
      pendingProposal.operation === "replacement",
  );
  const activeAgentField = fields.find(
    (field) => field.id === agentActiveFieldId,
  );
  const currentAgentFields = buildAgentRequestFields(
    fields,
    formValues,
    confirmedFieldIds,
    skippedFieldIds,
  );
  const hasUnansweredAgentField = currentAgentFields.some(
    (field) => field.status === "unanswered",
  );
  const confirmedAgentFieldCount = currentAgentFields.filter(
    (field) => field.status === "confirmed",
  ).length;
  const skippedAgentFieldCount = currentAgentFields.filter(
    (field) => field.status === "skipped",
  ).length;
  const reviewedAgentFieldCount =
    confirmedAgentFieldCount + skippedAgentFieldCount;
  const agentProgressPercentage = currentAgentFields.length
    ? Math.round(
        (reviewedAgentFieldCount / currentAgentFields.length) * 100,
      )
    : 0;
  const activeAgentFieldState = currentAgentFields.find(
    (field) => field.id === agentActiveFieldId,
  );
  const activeAgentFieldIndex = currentAgentFields.findIndex(
    (field) => field.id === agentActiveFieldId,
  );
  const activeAgentQuestion = activeAgentField
    ? activeAgentField.question ||
      activeAgentField.label ||
      humanizeFieldId(activeAgentField.id)
    : null;
  const activeAgentSection = activeAgentField?.section || formContext.title;
  const canAnswerActiveQuestion = Boolean(
    activeAgentField &&
      activeAgentFieldState?.status === "unanswered" &&
      !pendingProposal &&
      ["awaiting_answer", "awaiting_clarification"].includes(
        agentConversationState.phase,
      ),
  );
  const activeQuickAnswers = canAnswerActiveQuestion
    ? getQuickAnswerOptions(activeAgentField)
    : [];
  const visibleAgentMessages = showFullTranscript
    ? agentMessages
    : agentMessages.slice(-2);
  const latestAssistantTurn = getLatestAssistantTurn(agentMessages);
  const pendingProposalPdfField = fields.find(
    (field) => field.id === pendingProposal?.field_id,
  );
  const pendingProposalField =
    pendingProposalPdfField && isExplainableField(pendingProposalPdfField)
      ? pendingProposalPdfField
      : null;
  const activeProposalDetails =
    pendingProposalDetails &&
    pendingProposalDetails.field_id === pendingProposal?.field_id &&
    pendingProposalDetails.prepared_value === pendingProposal?.value
      ? pendingProposalDetails
      : null;
  const canApplyEditedProposal = Boolean(
    pendingProposalField &&
      isAgentValueCompatible(pendingProposalField, proposalEditValue),
  );
  const canUseOriginalProposal = Boolean(
    pendingProposalField &&
      activeProposalDetails &&
      activeProposalDetails.original_value !==
        activeProposalDetails.prepared_value &&
      isAgentValueCompatible(
        pendingProposalField,
        activeProposalDetails.original_value,
      ),
  );
  const canUseAgent =
    extractionStatus === "ready" && currentAgentFields.length > 0;
  const canStartAgent =
    agentConversationState.phase === "asking" && agentMessages.length === 0;
  const canResumeAgent = ["field_confirmed", "field_skipped"].includes(
    agentConversationState.phase,
  );
  const canSendAgentMessage = [
    "asking",
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
    "awaiting_replacement",
    "awaiting_replacement_confirmation",
    "form_complete",
  ].includes(agentConversationState.phase);
  const voiceInterview = useVoiceInterview({
    voice,
    agentIsBusy: agentStatus === "loading",
    agentHasError: agentStatus === "error",
    canSendMessage: canSendAgentMessage,
    needsAdvance:
      (canStartAgent || canResumeAgent) && hasUnansweredAgentField,
    latestAssistantTurn,
    activeFieldId: agentActiveFieldId,
    activeQuestion: activeAgentQuestion,
    hasPendingProposal: pendingProposal !== null,
    isFormComplete: agentConversationState.phase === "form_complete",
    onAdvance: () => sendAgentEvent({ type: "advance" }),
    onSendMessage: sendAgentMessage,
    onConfirmProposal: () => {
      if (pendingProposal) {
        confirmPendingProposal(pendingProposal.value);
      }
    },
    onRejectProposal: rejectPendingProposal,
    onSkipField: (fieldId) =>
      sendAgentEvent({ type: "skip", field_id: fieldId }),
  });

  return (
    <div className={`app-shell${selectedFile ? " document-loaded" : ""}`}>
      <header
        className={`app-header${selectedFile ? " workspace-header" : ""}`}
      >
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            F
          </span>
          <div>
            <p className="brand-name">Formless</p>
            <p className="brand-tagline">Voice-first form companion</p>
          </div>
        </div>

        {selectedFile ? (
          <>
            <div className="workspace-document-summary">
              <span>Current form</span>
              <strong title={selectedFile.name}>{selectedFile.name}</strong>
              {currentAgentFields.length > 0 ? (
                <small>
                  {reviewedAgentFieldCount} of {currentAgentFields.length}{" "}
                  questions reviewed
                </small>
              ) : (
                <small>{formatFileSize(selectedFile.size)}</small>
              )}
            </div>
            <div className="workspace-header-actions">
              <div
                className={`connection-status compact ${connectionStatus}`}
                aria-label={connectionCopy}
                title={connectionCopy}
              >
                <span className="status-dot" aria-hidden="true" />
                <span>API</span>
              </div>
              <label className="header-file-button">
                Change PDF
                <input
                  className="file-input"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={handleFileSelection}
                />
              </label>
              {downloadUrl ? (
                <a
                  className="header-download-button"
                  href={downloadUrl}
                  download={completedFilename}
                >
                  Download
                </a>
              ) : (
                <span
                  className="header-download-button disabled"
                  aria-disabled="true"
                  title="Confirm an answer to create a completed copy"
                >
                  Download
                </span>
              )}
            </div>
          </>
        ) : (
          <div className={`connection-status ${connectionStatus}`}>
            <span className="status-dot" aria-hidden="true" />
            <span>{connectionCopy}</span>
          </div>
        )}
      </header>

      <main
        className={`app-main${selectedFile ? " workspace-main" : " landing-main"}`}
      >
        {extractionError ? (
          <div className="error-banner" role="alert">
            <strong>Could not read this form.</strong>
            <span>{extractionError}</span>
          </div>
        ) : null}

        {!selectedFile ? (
          <section
            className="upload-landing"
            aria-labelledby="upload-landing-heading"
          >
            <div className="upload-landing-copy">
              <p className="eyebrow">A calmer way through forms</p>
              <h1 id="upload-landing-heading">
                Bring the form. We’ll fill it out together.
              </h1>
              <p className="upload-landing-intro">
                Formless stays beside you, asks one question at a time, and
                helps make confusing wording easier to understand.
              </p>
              <div className="upload-landing-actions">
                <label className="file-button">
                  Choose a fillable PDF
                  <input
                    className="file-input"
                    id="pdf-upload"
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={handleFileSelection}
                  />
                </label>
                <span>AcroForm PDF · Your original is never overwritten</span>
              </div>
              <ul
                className="upload-assurances"
                aria-label="How Formless works"
              >
                <li>
                  <span aria-hidden="true">1</span>
                  <div>
                    <strong>Talk naturally</strong>
                    <small>
                      Speak or type, and ask when a question is unclear.
                    </small>
                  </div>
                </li>
                <li>
                  <span aria-hidden="true">2</span>
                  <div>
                    <strong>Check every answer</strong>
                    <small>
                      Nothing reaches the PDF until you explicitly confirm it.
                    </small>
                  </div>
                </li>
                <li>
                  <span aria-hidden="true">3</span>
                  <div>
                    <strong>Keep the form in sight</strong>
                    <small>
                      Watch the completed copy update beside the conversation.
                    </small>
                  </div>
                </li>
              </ul>
            </div>
            <div className="upload-landing-visual" aria-hidden="true">
              <div className="landing-document">
                <span className="landing-document-heading" />
                <span />
                <span />
                <span className="landing-document-field" />
                <span />
                <span className="landing-document-field short" />
              </div>
              <div className="landing-conversation-card">
                <span className="landing-voice-orb" />
                <div>
                  <small>Formless</small>
                  <strong>Let’s take this one question at a time.</strong>
                </div>
              </div>
            </div>
          </section>
        ) : (
          <>
            <nav
              className="mobile-workspace-switch"
              aria-label="Choose workspace view"
            >
              <button
                type="button"
                aria-controls="assistant-workspace"
                aria-pressed={mobileWorkspaceView === "assistant"}
                onClick={() => setMobileWorkspaceView("assistant")}
              >
                Assistant
              </button>
              <button
                type="button"
                aria-controls="document-workspace"
                aria-pressed={mobileWorkspaceView === "form"}
                onClick={() => setMobileWorkspaceView("form")}
              >
                Form
              </button>
            </nav>
            <section
              className="workspace"
              data-mobile-view={mobileWorkspaceView}
            >
            <article
              className={`panel preview-panel mobile-workspace-view${
                mobileWorkspaceView === "form" ? " mobile-view-active" : ""
              }`}
              id="document-workspace"
            >
              <div className="panel-header">
                <div>
                  <p className="panel-kicker">Document</p>
                  <h2>PDF preview</h2>
                </div>
                <div className={`preview-status ${previewStatus}`} aria-live="polite">
                  <span className="status-dot" aria-hidden="true" />
                  <span>{previewCopy}</span>
                </div>
              </div>

              {previewUrl ? (
                <PdfViewer
                  key={originalUrlRef.current ?? selectedFile.name}
                  fileName={selectedFile.name}
                  isUpdating={previewStatus === "updating"}
                  url={previewUrl}
                />
              ) : null}

              {previewError ? (
                <p className="inline-error" role="alert">
                  {previewError} Your last successful preview is still shown.
                </p>
              ) : null}
            </article>

            <aside
              className={`panel fields-panel assistant-workspace mobile-workspace-view${
                mobileWorkspaceView === "assistant"
                  ? " mobile-view-active"
                  : ""
              }`}
              id="assistant-workspace"
            >
              <div className="panel-header assistant-heading">
                <div>
                  <p className="panel-kicker">Guided completion</p>
                  <h2>Form assistant</h2>
                </div>
                <div className="assistant-heading-actions">
                  {currentAgentFields.length > 0 ? (
                    <span className="assistant-progress-count">
                      {reviewedAgentFieldCount}/{currentAgentFields.length}
                    </span>
                  ) : null}
                  <details className="assistant-technology">
                    <summary>About</summary>
                    <p>
                      Natural-language help uses NVIDIA Nemotron through
                      Nebius. Every prepared answer still waits for your
                      explicit review.
                    </p>
                  </details>
                </div>
              </div>

              {currentAgentFields.length > 0 ? (
                <section
                  className="agent-progress-overview"
                  aria-label="Supported field progress"
                >
                  <div className="agent-progress-copy">
                    <span>Form progress</span>
                    <strong>
                      {reviewedAgentFieldCount} of {currentAgentFields.length}{" "}
                      reviewed
                    </strong>
                  </div>
                  <div
                    className="agent-progress-track"
                    role="progressbar"
                    aria-label="Reviewed supported fields"
                    aria-valuemin={0}
                    aria-valuemax={currentAgentFields.length}
                    aria-valuenow={reviewedAgentFieldCount}
                  >
                    <span style={{ width: `${agentProgressPercentage}%` }} />
                  </div>
                  <div className="agent-progress-breakdown">
                    <span>{confirmedAgentFieldCount} confirmed</span>
                    <span>{skippedAgentFieldCount} skipped</span>
                    <span>
                      {currentAgentFields.length - reviewedAgentFieldCount}{" "}
                      unanswered
                    </span>
                  </div>
                </section>
              ) : null}

              {extractionStatus === "loading" ? (
                <div className="workspace-status">
                  <div className="loading-state" aria-live="polite">
                    <span className="spinner" />
                    <div>
                      <strong>Reading form fields</strong>
                      <p>This should only take a moment.</p>
                    </div>
                  </div>
                </div>
              ) : null}

              {extractionStatus === "empty" ? (
                <div className="workspace-status">
                  <div className="message-state">
                    <strong>No fillable fields found</strong>
                    <p>Try another PDF that contains AcroForm fields.</p>
                  </div>
                </div>
              ) : null}

              {extractionStatus === "error" ? (
                <div className="workspace-status">
                  <div className="message-state" role="alert">
                    <strong>Fields unavailable</strong>
                    <p>The original PDF is still available in the preview.</p>
                  </div>
                </div>
              ) : null}

              <section
                className={`ai-explanation-panel agent-panel ${agentStatus}`}
                aria-busy={agentStatus === "loading"}
                aria-live="polite"
              >
                {canUseAgent ? (
                  <VoiceAssistantPanel
                    voice={voice}
                    interview={voiceInterview}
                    agentIsBusy={agentStatus === "loading"}
                    hasPendingProposal={pendingProposal !== null}
                  />
                ) : null}

                {activeAgentField && activeAgentQuestion ? (
                  <section
                    className={`guided-question-card ${agentConversationState.phase}`}
                    aria-labelledby="active-question-heading"
                  >
                    <div className="guided-question-meta">
                      <div>
                        {activeAgentSection ? (
                          <span>{activeAgentSection}</span>
                        ) : (
                          <span>Guided interview</span>
                        )}
                        {activeAgentField.page ? (
                          <span>Page {activeAgentField.page}</span>
                        ) : null}
                      </div>
                      {activeAgentFieldIndex >= 0 ? (
                        <strong>
                          Question {activeAgentFieldIndex + 1} of{" "}
                          {currentAgentFields.length}
                        </strong>
                      ) : null}
                    </div>

                    <div className="guided-question-copy">
                      <span>
                        {getQuestionStatusLabel(agentConversationState.phase)}
                      </span>
                      <h3 id="active-question-heading">
                        {activeAgentQuestion}
                      </h3>
                      {activeAgentField.help_text ? (
                        <p>{activeAgentField.help_text}</p>
                      ) : null}
                    </div>

                    {canAnswerActiveQuestion &&
                    activeQuickAnswers.length > 0 ? (
                      <fieldset className="agent-quick-answers">
                        <legend>Quick answers</legend>
                        {activeQuickAnswers.length <= 6 ? (
                          <div>
                            {activeQuickAnswers.map((answer) => (
                              <button
                                key={answer.value}
                                type="button"
                                disabled={agentStatus === "loading"}
                                onClick={() => sendAgentMessage(answer.message)}
                              >
                                {answer.label}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <label>
                            <span>Choose an available answer</span>
                            <select
                              key={`${activeAgentField.id}-${agentMessages.length}`}
                              defaultValue=""
                              disabled={agentStatus === "loading"}
                              onChange={(event) => {
                                if (event.target.value) {
                                  sendAgentMessage(event.target.value);
                                }
                              }}
                            >
                              <option value="" disabled>
                                Select an option
                              </option>
                              {activeQuickAnswers.map((answer) => (
                                <option
                                  key={answer.value}
                                  value={answer.message}
                                >
                                  {answer.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        <small>You can still type your answer below.</small>
                      </fieldset>
                    ) : null}

                    {canAnswerActiveQuestion ? (
                      <div
                        className="guided-question-actions"
                        aria-label="Help with this question"
                      >
                        <button
                          type="button"
                          disabled={agentStatus === "loading"}
                          onClick={() =>
                            sendAgentMessage(
                              "Explain this question in plain language.",
                            )
                          }
                        >
                          Explain this
                        </button>
                        <button
                          type="button"
                          disabled={agentStatus === "loading"}
                          onClick={() =>
                            sendAgentMessage(
                              "Check official guidance for this question.",
                            )
                          }
                        >
                          Check guidance
                        </button>
                        <button
                          type="button"
                          disabled={agentStatus === "loading"}
                          onClick={() =>
                            sendAgentEvent({
                              type: "skip",
                              field_id: activeAgentField.id,
                            })
                          }
                        >
                          Skip for now
                        </button>
                      </div>
                    ) : null}
                  </section>
                ) : null}

                {agentMessages.length === 0 ? (
                  <p className="ai-explanation-empty">
                    Start a guided conversation, or choose{" "}
                    <strong>Explain with AI</strong> on a field. Suggestions
                    stay separate from your form until you explicitly confirm
                    or edit them.
                  </p>
                ) : null}

                {agentMessages.length > 0 ? (
                  <section className="agent-transcript">
                    <div className="agent-transcript-heading">
                      <div>
                        <strong>Conversation</strong>
                        <span>{agentMessages.length} messages</span>
                      </div>
                      {agentMessages.length > 2 ? (
                        <button
                          type="button"
                          aria-controls="agent-conversation-log"
                          aria-expanded={showFullTranscript}
                          onClick={() =>
                            setShowFullTranscript((current) => !current)
                          }
                        >
                          {showFullTranscript
                            ? "Show recent only"
                            : "Show full transcript"}
                        </button>
                      ) : null}
                    </div>
                    <div
                      className="agent-conversation"
                      id="agent-conversation-log"
                      aria-label="Form assistant conversation"
                      role="log"
                    >
                      {visibleAgentMessages.map((message) => {
                        const messageField = fields.find(
                          (field) => field.id === message.fieldId,
                        );
                        const hasGuidance = Boolean(
                          message.guidance?.length || message.webGuidance,
                        );

                        return (
                          <article
                            className={[
                              "agent-message",
                              message.role,
                              message.effect?.effect ?? "",
                            ]
                              .filter(Boolean)
                              .join(" ")}
                            key={message.id}
                          >
                            <div className="agent-message-meta">
                              <strong>
                                {message.role === "user"
                                  ? "You"
                                  : "Form assistant"}
                              </strong>
                              <div>
                                {messageField ? (
                                  <span>
                                    {messageField.label ||
                                      humanizeFieldId(messageField.id)}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <p>{message.content}</p>
                            {hasGuidance ? (
                              <details className="agent-guidance-disclosure">
                                <summary>View guidance and sources</summary>
                                <div>
                                  {message.guidance?.map((citation) => (
                                    <aside
                                      className="agent-guidance"
                                      key={`${message.id}-${citation.source_id}-${citation.excerpt}`}
                                    >
                                      <span>
                                        Official guidance · paraphrased
                                      </span>
                                      <p>{citation.excerpt}</p>
                                      <a
                                        href={citation.url}
                                        rel="noreferrer"
                                        target="_blank"
                                      >
                                        {citation.title}
                                      </a>
                                      <small>
                                        {citation.organization} · Form version{" "}
                                        {citation.form_version} · Retrieved{" "}
                                        {citation.retrieved_at}
                                      </small>
                                    </aside>
                                  ))}
                                  {message.webGuidance &&
                                  message.webGuidance.sources.length > 0 ? (
                                    <aside
                                      className={`agent-web-guidance ${message.webGuidance.status}`}
                                    >
                                      <span>Live web guidance · Tavily</span>
                                      <p>{message.webGuidance.notice}</p>
                                      {message.webGuidance.sources.map(
                                        (source) => (
                                          <article
                                            className="agent-web-source"
                                            key={`${message.id}-${source.source_id}`}
                                          >
                                            <a
                                              href={source.url}
                                              rel="noreferrer"
                                              target="_blank"
                                            >
                                              {source.title}
                                            </a>
                                            <p>{source.snippet}</p>
                                            <small>
                                              {getWebSourceQualityLabel(
                                                source.source_quality,
                                              )} · {source.hostname} · Retrieved{" "}
                                              {source.retrieved_at}
                                              {source.form_version
                                                ? ` · Form version ${source.form_version}`
                                                : ""}
                                            </small>
                                          </article>
                                        ),
                                      )}
                                    </aside>
                                  ) : null}
                                  {message.webGuidance &&
                                  message.webGuidance.sources.length === 0 &&
                                  message.webGuidanceRetry ? (
                                    <div className="agent-guidance-recovery">
                                      <button
                                        type="button"
                                        disabled={agentStatus === "loading"}
                                        onClick={() =>
                                          void requestAgent(
                                            message.webGuidanceRetry as AgentRequest,
                                          )
                                        }
                                      >
                                        Retry guidance check
                                      </button>
                                    </div>
                                  ) : null}
                                </div>
                              </details>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ) : null}

                {pendingProposal && pendingProposalField ? (
                  <section
                    className="agent-confirmation"
                    aria-label="Review proposed answer"
                  >
                    <div className="agent-confirmation-heading">
                      <div>
                        <span>
                          {isReplacementPending
                            ? "Review replacement"
                            : "Review proposal"}
                        </span>
                        <strong>
                          {pendingProposalField.question ||
                            pendingProposalField.label ||
                            humanizeFieldId(pendingProposalField.id)}
                        </strong>
                      </div>
                      <span className="agent-confirmation-status">
                        Awaiting your review
                      </span>
                    </div>

                    {isEditingProposal ? (
                      <form
                        className="agent-proposal-edit"
                        onSubmit={(event) => {
                          event.preventDefault();
                          if (canApplyEditedProposal) {
                            confirmPendingProposal(proposalEditValue);
                          }
                        }}
                      >
                        <ProposalValueEditor
                          field={pendingProposalField}
                          value={proposalEditValue}
                          onChange={setProposalEditValue}
                        />
                        <div className="agent-confirmation-actions">
                          <button
                            className="primary"
                            type="submit"
                            disabled={
                              agentStatus === "loading" ||
                              !canApplyEditedProposal
                            }
                          >
                            Confirm edited answer
                          </button>
                          <button
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={() => {
                              setProposalEditValue(pendingProposal.value);
                              setIsEditingProposal(false);
                            }}
                          >
                            Cancel edit
                          </button>
                        </div>
                      </form>
                    ) : (
                      <>
                        {activeProposalDetails?.effect ===
                        "replacement_proposal" ? (
                          <div className="agent-confirmation-value">
                            <span>Current confirmed answer</span>
                            <strong>
                              {formatAgentValue(
                                activeProposalDetails.previous_confirmed_value,
                              )}
                            </strong>
                          </div>
                        ) : null}
                        {activeProposalDetails?.transformation ? (
                          <div className="agent-preparation-comparison">
                            <div>
                              <span>You said</span>
                              <strong>
                                {formatAgentValue(
                                  activeProposalDetails.original_value,
                                )}
                              </strong>
                            </div>
                            <div>
                              <span>Prepared for the form</span>
                              <strong>
                                {formatAgentValue(
                                  activeProposalDetails.prepared_value,
                                )}
                              </strong>
                            </div>
                            <small>
                              {activeProposalDetails.transformation}
                            </small>
                          </div>
                        ) : (
                          <div className="agent-confirmation-value">
                            <span>Prepared answer</span>
                            <strong>
                              {formatAgentValue(pendingProposal.value)}
                            </strong>
                          </div>
                        )}
                        <p>
                          {isReplacementPending
                            ? "Your current confirmed answer and PDF stay unchanged until you confirm this replacement."
                            : "This answer has not been added to the PDF. Review it, then confirm or edit it."}
                        </p>
                        <div className="agent-confirmation-actions">
                          <button
                            className="primary"
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={() =>
                              confirmPendingProposal(pendingProposal.value)
                            }
                          >
                            {isReplacementPending
                              ? "Confirm replacement"
                              : "Confirm"}
                          </button>
                          <button
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={() => {
                              setProposalEditValue(pendingProposal.value);
                              setIsEditingProposal(true);
                            }}
                          >
                            Edit
                          </button>
                          {canUseOriginalProposal ? (
                            <button
                              type="button"
                              disabled={agentStatus === "loading"}
                              onClick={useOriginalProposal}
                            >
                              Use original
                            </button>
                          ) : null}
                          <button
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={rejectPendingProposal}
                          >
                            Reject
                          </button>
                          {isReplacementPending ? (
                            <button
                              type="button"
                              disabled={agentStatus === "loading"}
                              onClick={() =>
                                sendAgentEvent({
                                  type: "cancel_correction",
                                })
                              }
                            >
                              Cancel correction
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled={agentStatus === "loading"}
                              onClick={skipPendingProposal}
                            >
                              Skip field
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </section>
                ) : null}

                {agentStatus === "loading" ? (
                  <div className="ai-explanation-state">
                    <span className="spinner" aria-hidden="true" />
                    <span>
                      {agentActivity === "guidance"
                        ? "Checking reviewed and live guidance…"
                        : "Form assistant is thinking…"}
                    </span>
                  </div>
                ) : null}

                {agentStatus === "error" && agentError ? (
                  <div className="ai-explanation-error" role="alert">
                    <p>{agentError}</p>
                    {failedAgentRequest ? (
                      <button
                        type="button"
                        onClick={() => void requestAgent(failedAgentRequest)}
                      >
                        {agentRequestNeedsExternalGuidance(failedAgentRequest)
                          ? "Retry guidance search"
                          : "Retry message"}
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {canUseAgent &&
                (canStartAgent || canResumeAgent) &&
                hasUnansweredAgentField &&
                agentStatus !== "loading" ? (
                  <button
                    className="agent-progress-button secondary"
                    type="button"
                    onClick={() => sendAgentEvent({ type: "advance" })}
                  >
                    {canStartAgent
                      ? "Start with typing"
                      : "Continue with typing"}
                  </button>
                ) : null}

                {canUseAgent &&
                agentConversationState.phase === "form_complete" ? (
                  <section
                    className="agent-complete-state"
                    aria-labelledby="agent-complete-heading"
                  >
                    <span>Interview complete</span>
                    <h3 id="agent-complete-heading">
                      Every supported question has been reviewed.
                    </h3>
                    <p>
                      {confirmedAgentFieldCount} confirmed ·{" "}
                      {skippedAgentFieldCount} skipped · 0 unanswered
                    </p>
                    <div className="agent-complete-actions">
                      <button
                        type="button"
                        disabled={agentStatus === "loading"}
                        onClick={() =>
                          sendAgentMessage(
                            "Show confirmed, skipped, and unanswered fields.",
                          )
                        }
                      >
                        Review answers
                      </button>
                      <button
                        type="button"
                        disabled={agentStatus === "loading"}
                        onClick={() => {
                          setAgentInput("Change ");
                          window.requestAnimationFrame(() =>
                            agentInputRef.current?.focus(),
                          );
                        }}
                      >
                        Correct an answer
                      </button>
                    </div>
                  </section>
                ) : null}

              </section>

              {canUseAgent ? (
                <form
                  className="ai-question-form agent-message-form"
                  onSubmit={submitAgentMessage}
                >
                  <label htmlFor="agent-message">
                    {activeAgentField
                      ? pendingProposal
                        ? "Ask a question or use the review controls"
                        : "Your answer or question"
                      : agentConversationState.phase === "form_complete"
                        ? "Ask about your answers or name one to correct"
                        : "Type to use the assistant without voice"}
                  </label>
                  <div className="ai-question-controls">
                    <input
                      ref={agentInputRef}
                      id="agent-message"
                      type="text"
                      maxLength={2000}
                      placeholder={
                        activeAgentField
                          ? pendingProposal
                            ? "Ask about this proposal"
                            : "Type your answer or ask for help"
                          : agentConversationState.phase === "form_complete"
                            ? "For example: Change my home address"
                            : "Ask for help with the form"
                      }
                      value={agentInput}
                      disabled={
                        agentStatus === "loading" || !canSendAgentMessage
                      }
                      onChange={(event) => setAgentInput(event.target.value)}
                    />
                    <button
                      type="submit"
                      disabled={
                        agentStatus === "loading" ||
                        !agentInput.trim() ||
                        !canSendAgentMessage
                      }
                    >
                      Send
                    </button>
                  </div>
                  <small>
                    Prepared answers only reach the PDF after your explicit
                    confirmation.
                  </small>
                </form>
              ) : extractionStatus === "ready" ? (
                <p className="agent-complete-state">
                  This form has no fields supported by the assistant.
                </p>
              ) : null}

              <section className="manual-fields-drawer">
                <button
                  className="manual-drawer-toggle"
                  type="button"
                  aria-controls="manual-fields-panel"
                  aria-expanded={manualDrawerOpen}
                  disabled={
                    extractionStatus !== "ready" || fields.length === 0
                  }
                  onClick={() => setManualDrawerOpen((current) => !current)}
                >
                  <span className="manual-drawer-copy">
                    <strong>Edit all fields</strong>
                    <small>
                      Manual fallback
                      {fields.length > 0 ? ` · ${fields.length} fields` : ""}
                    </small>
                  </span>
                  <span
                    className={`manual-drawer-chevron${
                      manualDrawerOpen ? " open" : ""
                    }`}
                    aria-hidden="true"
                  >
                    ⌄
                  </span>
                </button>

                <div
                  className="fields-content manual-fields-content"
                  id="manual-fields-panel"
                  hidden={!manualDrawerOpen}
                >
                  {extractionStatus === "ready" ? (
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
                            {group.page
                              ? `Page ${group.page}`
                              : "Other fields"}
                          </h3>
                          <div className="page-field-list">
                            {group.fields.map(({ field, index }) => {
                              const isActiveForAgent =
                                agentActiveFieldId === field.id;
                              const agentFieldState = currentAgentFields.find(
                                (candidate) => candidate.id === field.id,
                              );
                              const isAskingAgent =
                                isActiveForAgent &&
                                agentStatus === "loading";

                              return (
                                <div
                                  className={`field-item${
                                    isActiveForAgent
                                      ? " active-for-agent"
                                      : ""
                                  }`}
                                  key={field.id}
                                >
                                  <FieldControl
                                    field={field}
                                    inputId={`pdf-field-${index}`}
                                    value={formValues[field.id]}
                                    onChange={(value) =>
                                      updateField(field.id, value)
                                    }
                                  />
                                  {isExplainableField(field) ? (
                                    <button
                                      className="explain-field-button"
                                      type="button"
                                      disabled={
                                        agentStatus === "loading" ||
                                        pendingProposal !== null ||
                                        agentFieldState?.status !== "unanswered"
                                      }
                                      aria-label={`Explain ${
                                        field.label || humanizeFieldId(field.id)
                                      } with AI`}
                                      onClick={() => {
                                        const message =
                                          "Please explain this field in plain language.";
                                        sendAgentEvent(
                                          {
                                            type: "focus_field",
                                            field_id: field.id,
                                            content: message,
                                          },
                                          message,
                                        );
                                      }}
                                    >
                                      <span aria-hidden="true">✦</span>
                                      {isAskingAgent
                                        ? "Asking…"
                                        : "Explain with AI"}
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
            </aside>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

type FieldControlProps = {
  field: PdfField;
  inputId: string;
  value: FieldValue | undefined;
  onChange: (value: FieldValue) => void;
};

function FieldControl({ field, inputId, value, onChange }: FieldControlProps) {
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

function ProposalValueEditor({
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

async function readApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall back to the status-based message below.
  }

  return `Request failed with status ${response.status}.`;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function humanizeFieldId(fieldId: string): string {
  const words = fieldId.replace(/[._-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function isExplainableField(
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

function getInitialFieldValue(field: PdfField): FieldValue {
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

function hasInitialConfirmedValue(field: PdfField): boolean {
  if (!isExplainableField(field) || field.value === undefined) {
    return false;
  }

  if (field.type === "checkbox") {
    return field.value === true;
  }

  return isAgentValueCompatible(field, field.value);
}

function isManuallyConfirmedValue(
  field: PdfField,
  value: FieldValue,
): boolean {
  return isExplainableField(field) && isAgentValueCompatible(field, value);
}

function buildAgentRequestFields(
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

function isAgentValueCompatible(
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

function getAvailableDropdownOptions(options?: string[]): string[] {
  return (options ?? []).filter(
    (option) => !isPlaceholderDropdownOption(option),
  );
}

function getQuickAnswerOptions(
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

function parseAgentResponse(
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
    (["asking", "form_complete"].includes(state.phase) &&
      state.active_field_id !== null) ||
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
    (![
      "awaiting_confirmation",
      "awaiting_replacement_confirmation",
    ].includes(state.phase) &&
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

  if (
    !isResolutionEffect &&
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
    (effect.effect === "none" &&
      [
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

function findAgentField(
  fields: AgentRequestField[],
  fieldId: string,
): AgentRequestField | undefined {
  return fields.find((field) => field.id === fieldId);
}

function isAgentEffectKind(value: unknown): value is AgentEffectKind {
  return [
    "none",
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

function isValidFormContext(value: unknown): value is FormContext {
  if (!isRecord(value) || !Array.isArray(value.instructions)) {
    return false;
  }
  if (
    value.title !== undefined &&
    value.title !== null &&
    typeof value.title !== "string"
  ) {
    return false;
  }
  if (
    value.form_id !== undefined &&
    value.form_id !== null &&
    typeof value.form_id !== "string"
  ) {
    return false;
  }
  if (
    value.form_version !== undefined &&
    value.form_version !== null &&
    typeof value.form_version !== "string"
  ) {
    return false;
  }
  const hasFormId = typeof value.form_id === "string";
  const hasFormVersion = typeof value.form_version === "string";
  if (hasFormId !== hasFormVersion) {
    return false;
  }
  return value.instructions.every(
    (instruction) => typeof instruction === "string",
  );
}

function getQuestionStatusLabel(phase: ConversationPhase): string {
  const labels: Record<ConversationPhase, string> = {
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

function getLatestAssistantTurn(
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

function getWebSourceQualityLabel(
  quality: WebGuidanceCitation["source_quality"],
): string {
  return {
    issuing_organization: "Known issuing-organisation source",
    public_authority: "Public-authority source",
    general_web: "General web source",
  }[quality];
}

function agentRequestNeedsExternalGuidance(request: AgentRequest): boolean {
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

function createInitialConversationState(): ConversationState {
  return {
    phase: "asking",
    active_field_id: null,
    pending_proposal: null,
    remembered_candidates: [],
  };
}

function formatAgentValue(value: FieldValue): string {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return value;
}

function groupFieldsByPage(fields: PdfField[]): PageFieldGroup[] {
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default App;
