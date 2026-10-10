import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import PdfViewer from "./PdfViewer";

type ConnectionStatus = "checking" | "connected" | "disconnected";
type ExtractionStatus = "idle" | "loading" | "ready" | "empty" | "error";
type PreviewStatus = "idle" | "pending" | "updating" | "ready" | "error";
type AgentStatus = "idle" | "loading" | "error";
type FieldValue = string | boolean;
type AgentActionKind =
  | "explain"
  | "clarify"
  | "propose"
  | "skip"
  | "next"
  | "confirmed"
  | "rejected";
type AgentFieldStatus = "unanswered" | "confirmed" | "skipped";
type ConversationPhase =
  | "asking"
  | "awaiting_answer"
  | "awaiting_clarification"
  | "awaiting_confirmation"
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
  page?: number;
  options?: string[];
  value?: FieldValue;
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

type PendingProposal = {
  field_id: string;
  value: FieldValue;
};

type ConversationState = {
  phase: ConversationPhase;
  active_field_id: string | null;
  pending_proposal: PendingProposal | null;
};

type AgentEvent =
  | { type: "advance" }
  | { type: "message"; content: string }
  | { type: "focus_field"; field_id: string; content: string }
  | { type: "confirm" }
  | { type: "confirm_edit"; value: FieldValue }
  | { type: "reject" }
  | { type: "skip"; field_id: string };

type AgentAction =
  | {
      action: Exclude<
        AgentActionKind,
        "propose" | "next" | "confirmed"
      >;
      message: string;
      field_id: string;
    }
  | {
      action: "propose";
      message: string;
      field_id: string;
      value: FieldValue;
    }
  | {
      action: "next";
      message: string;
      field_id: string | null;
    }
  | {
      action: "confirmed";
      message: string;
      field_id: string;
      value: FieldValue;
    };

type AgentResponse = {
  action: AgentAction;
  conversation_state: ConversationState;
  guidance: OfficialGuidanceCitation[];
};

type ConversationMessage = AgentHistoryMessage & {
  id: number;
  action?: AgentActionKind;
  fieldId?: string | null;
  proposedValue?: FieldValue;
  guidance?: OfficialGuidanceCitation[];
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
  const [agentInput, setAgentInput] = useState("");
  const [agentError, setAgentError] = useState<string | null>(null);
  const [failedAgentRequest, setFailedAgentRequest] =
    useState<AgentRequest | null>(null);
  const [isEditingProposal, setIsEditingProposal] = useState(false);
  const [proposalEditValue, setProposalEditValue] =
    useState<FieldValue>("");
  const [manualDrawerOpen, setManualDrawerOpen] = useState(false);

  const originalUrlRef = useRef<string | null>(null);
  const filledUrlRef = useRef<string | null>(null);
  const extractionControllerRef = useRef<AbortController | null>(null);
  const agentControllerRef = useRef<AbortController | null>(null);
  const agentRequestInFlightRef = useRef(false);
  const agentMessageIdRef = useRef(0);

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
    setAgentInput("");
    setAgentError(null);
    setFailedAgentRequest(null);
    setIsEditingProposal(false);
    setProposalEditValue("");
    setManualDrawerOpen(false);
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
    if (!field) {
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
    setAgentMessages((current) =>
      [...current, nextMessage].slice(-maxAgentHistoryMessages),
    );
  }

  async function requestAgent(request: AgentRequest) {
    if (agentRequestInFlightRef.current) {
      return;
    }

    agentRequestInFlightRef.current = true;
    const controller = new AbortController();
    agentControllerRef.current = controller;
    setAgentStatus("loading");
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
      );
      const { action, conversation_state: conversationState } = agentResponse;

      if (controller.signal.aborted) {
        return;
      }

      appendAgentMessage({
        role: "assistant",
        content: action.message,
        action: action.action,
        fieldId: action.field_id,
        guidance: agentResponse.guidance,
        ...(action.action === "propose"
          ? { proposedValue: action.value }
          : {}),
      });

      setAgentConversationState(conversationState);

      if (action.action === "propose") {
        setProposalEditValue(action.value);
        setIsEditingProposal(false);
      } else if (action.action === "confirmed") {
        writeFieldValue(action.field_id, action.value, true);
        resetProposalEditor();
      } else if (action.action === "skip") {
        const skippedField = request.fields.find(
          (field) => field.id === action.field_id,
        );
        if (skippedField?.status === "unanswered") {
          setSkippedFieldIds((current) =>
            new Set(current).add(action.field_id),
          );
        }
        setConfirmedFieldIds((current) => {
          const next = new Set(current);
          next.delete(action.field_id);
          return next;
        });
        resetProposalEditor();
      } else if (conversationState.phase !== "awaiting_confirmation") {
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
    checking: "Checking API",
    connected: "API connected",
    disconnected: "API unavailable",
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
  const pendingProposalPdfField = fields.find(
    (field) => field.id === pendingProposal?.field_id,
  );
  const pendingProposalField =
    pendingProposalPdfField && isExplainableField(pendingProposalPdfField)
      ? pendingProposalPdfField
      : null;
  const canApplyEditedProposal = Boolean(
    pendingProposalField &&
      isAgentValueCompatible(pendingProposalField, proposalEditValue),
  );
  const canUseAgent =
    extractionStatus === "ready" && currentAgentFields.length > 0;
  const canAdvanceAgent = [
    "asking",
    "field_confirmed",
    "field_skipped",
  ].includes(agentConversationState.phase);
  const canSendAgentMessage = [
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
  ].includes(agentConversationState.phase);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            F
          </span>
          <div>
            <p className="brand-name">Formless</p>
            <p className="brand-tagline">AI-assisted PDF workspace</p>
          </div>
        </div>

        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{connectionCopy}</span>
        </div>
      </header>

      <main className="app-main">
        <section className="intro-panel">
          <div className="intro-copy">
            <p className="eyebrow">Fill with confidence</p>
            <h1>Understand your form as you fill it.</h1>
            <p>
              Choose a fillable PDF, ask the assistant to explain confusing
              fields, and download a completed copy. Your original stays
              unchanged.
            </p>
          </div>

          <div className="upload-area">
            <label className="file-button">
              {selectedFile ? "Choose another PDF" : "Choose a fillable PDF"}
              <input
                className="file-input"
                id="pdf-upload"
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileSelection}
              />
            </label>
            {selectedFile ? (
              <div className="selected-file">
                <span className="file-icon" aria-hidden="true">
                  PDF
                </span>
                <span>
                  <strong>{selectedFile.name}</strong>
                  <small>{formatFileSize(selectedFile.size)}</small>
                </span>
              </div>
            ) : (
              <p>PDF files stay in this browser session.</p>
            )}
          </div>
        </section>

        {extractionError ? (
          <div className="error-banner" role="alert">
            <strong>Could not read this form.</strong>
            <span>{extractionError}</span>
          </div>
        ) : null}

        {!selectedFile ? (
          <section className="empty-workspace">
            <div className="empty-preview" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div>
              <p className="eyebrow">Ready when you are</p>
              <h2>Your PDF workspace will appear here.</h2>
              <p>
                The document preview and guided assistant will sit side by
                side.
              </p>
            </div>
          </section>
        ) : (
          <section className="workspace">
            <article className="panel preview-panel">
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

            <aside className="panel fields-panel assistant-workspace">
              <div className="panel-header assistant-heading">
                <div>
                  <p className="panel-kicker">Guided completion</p>
                  <h2>Form assistant</h2>
                </div>
                {currentAgentFields.length > 0 ? (
                  <span className="assistant-progress-count">
                    {reviewedAgentFieldCount}/{currentAgentFields.length}
                  </span>
                ) : null}
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
                <div className="ai-explanation-heading">
                  <span className="ai-mark" aria-hidden="true">
                    AI
                  </span>
                  <div>
                    <strong>Form assistant</strong>
                    <span>NVIDIA Nemotron via Nebius Token Factory</span>
                  </div>
                </div>

                {activeAgentField ? (
                  <div className="ai-selected-field">
                    <div>
                      <span>Active field</span>
                      <strong>
                        {activeAgentField.label ||
                          humanizeFieldId(activeAgentField.id)}
                      </strong>
                    </div>
                    {activeAgentFieldState?.status === "unanswered" &&
                    !pendingProposal &&
                    ["awaiting_answer", "awaiting_clarification"].includes(
                      agentConversationState.phase,
                    ) ? (
                      <button
                        className="agent-skip-button"
                        type="button"
                        disabled={agentStatus === "loading"}
                        onClick={() =>
                          sendAgentEvent({
                            type: "skip",
                            field_id: activeAgentField.id,
                          })
                        }
                      >
                        Skip
                      </button>
                    ) : null}
                  </div>
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
                  <div
                    className="agent-conversation"
                    aria-label="Recent form assistant conversation"
                    role="log"
                  >
                    {agentMessages.map((message) => {
                      const messageField = fields.find(
                        (field) => field.id === message.fieldId,
                      );

                      return (
                        <article
                          className={[
                            "agent-message",
                            message.role,
                            message.action ?? "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                          key={message.id}
                        >
                          <div className="agent-message-meta">
                            <strong>
                              {message.role === "user"
                                ? "You"
                                : getAgentActionLabel(message.action)}
                            </strong>
                            {messageField ? (
                              <span>
                                {messageField.label ||
                                  humanizeFieldId(messageField.id)}
                              </span>
                            ) : null}
                          </div>
                          {message.guidance?.length ? (
                            <span className="agent-explanation-label">
                              Assistant explanation
                            </span>
                          ) : null}
                          <p>{message.content}</p>
                          {message.guidance?.map((citation) => (
                            <aside
                              className="agent-guidance"
                              key={`${message.id}-${citation.source_id}-${citation.excerpt}`}
                            >
                              <span>Official guidance · paraphrased</span>
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
                          {message.action === "propose" &&
                          message.proposedValue !== undefined ? (
                            <div className="agent-proposal">
                              <span>Proposed answer</span>
                              <strong>
                                {formatAgentValue(message.proposedValue)}
                              </strong>
                              <small>
                                This suggestion never changes the field or PDF
                                automatically.
                              </small>
                            </div>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                ) : null}

                {pendingProposal && pendingProposalField ? (
                  <section
                    className="agent-confirmation"
                    aria-label="Review proposed answer"
                  >
                    <div className="agent-confirmation-heading">
                      <div>
                        <span>Review proposal</span>
                        <strong>
                          {pendingProposalField.label ||
                            humanizeFieldId(pendingProposalField.id)}
                        </strong>
                        <code>{pendingProposalField.id}</code>
                      </div>
                      <span className="agent-confirmation-status">
                        Awaiting confirmation
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
                            Use edited answer
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
                        <div className="agent-confirmation-value">
                          <span>Proposed answer</span>
                          <strong>
                            {formatAgentValue(pendingProposal.value)}
                          </strong>
                        </div>
                        <p>
                          Nothing changes until you choose Confirm or submit an
                          edited answer.
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
                            Confirm
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
                          <button
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={rejectPendingProposal}
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            disabled={agentStatus === "loading"}
                            onClick={skipPendingProposal}
                          >
                            Skip field
                          </button>
                        </div>
                      </>
                    )}
                  </section>
                ) : null}

                {agentStatus === "loading" ? (
                  <div className="ai-explanation-state">
                    <span className="spinner" aria-hidden="true" />
                    <span>Form assistant is thinking…</span>
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
                        Retry message
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {canUseAgent &&
                canAdvanceAgent &&
                hasUnansweredAgentField &&
                agentStatus !== "loading" ? (
                  <button
                    className="agent-progress-button"
                    type="button"
                    onClick={() => sendAgentEvent({ type: "advance" })}
                  >
                    {agentMessages.length === 0
                      ? "Start guided form"
                      : "Continue to next field"}
                  </button>
                ) : null}

                {canUseAgent &&
                agentConversationState.phase === "form_complete" ? (
                  <p className="agent-complete-state">
                    No unanswered supported fields remain.
                  </p>
                ) : null}

                {canUseAgent ? (
                  <form
                    className="ai-question-form agent-message-form"
                    onSubmit={submitAgentMessage}
                  >
                    <label htmlFor="agent-message">
                      {activeAgentField
                        ? "Reply or ask a follow-up"
                        : "Start or continue the guided form"}
                    </label>
                    <div className="ai-question-controls">
                      <input
                        id="agent-message"
                        type="text"
                        maxLength={2000}
                        placeholder={
                          activeAgentField
                            ? "Type your answer or ask for clarification"
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
                      Only the eight most recent messages are kept. AI
                      proposals update the form only after you explicitly
                      confirm or use an edited answer.
                    </small>
                  </form>
                ) : extractionStatus === "ready" ? (
                  <p className="agent-complete-state">
                    This form has no fields supported by the assistant.
                  </p>
                ) : null}
              </section>

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

              <div className="fields-footer">
                <p>
                  {downloadUrl
                    ? "Your latest changes are ready to download."
                    : "Confirm an answer or edit a field to create a completed copy."}
                </p>
                {downloadUrl ? (
                  <a
                    className="download-button"
                    href={downloadUrl}
                    download={completedFilename}
                  >
                    Download completed PDF
                  </a>
                ) : (
                  <span className="download-button disabled" aria-disabled="true">
                    Download completed PDF
                  </span>
                )}
              </div>
            </aside>
          </section>
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
  return ["text", "textarea", "number", "dropdown", "checkbox"].includes(
    field.type,
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
  field: PdfField & { type: AgentFieldType },
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
): AgentResponse {
  if (!isRecord(payload)) {
    throw new Error("The API returned an invalid form assistant response.");
  }

  const action = parseAgentAction(payload.action, requestFields);
  const conversationState = parseConversationState(
    payload.conversation_state,
    requestFields,
  );
  const guidance = parseOfficialGuidance(payload.guidance);
  validateAgentResponseState(action, conversationState, requestFields);
  return {
    action,
    conversation_state: conversationState,
    guidance,
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

function parseAgentAction(
  payload: unknown,
  requestFields: AgentRequestField[],
): AgentAction {
  if (!isRecord(payload) || !isAgentActionKind(payload.action)) {
    throw new Error("The API returned an invalid form assistant response.");
  }

  if (typeof payload.message !== "string" || !payload.message.trim()) {
    throw new Error("The API returned an invalid form assistant response.");
  }

  const message = payload.message.trim();
  const fieldId = payload.field_id;

  if (payload.action === "next") {
    if (fieldId !== null && typeof fieldId !== "string") {
      throw new Error("The API returned an invalid form assistant response.");
    }
    if (typeof fieldId === "string" && !findAgentField(requestFields, fieldId)) {
      throw new Error("The form assistant returned an unknown field.");
    }
    return { action: "next", message, field_id: fieldId };
  }

  if (typeof fieldId !== "string") {
    throw new Error("The API returned an invalid form assistant response.");
  }

  const field = findAgentField(requestFields, fieldId);
  if (!field) {
    throw new Error("The form assistant returned an unknown field.");
  }

  if (payload.action === "propose" || payload.action === "confirmed") {
    const value = payload.value;
    if (
      (typeof value !== "string" && typeof value !== "boolean") ||
      !isAgentValueCompatible(field, value)
    ) {
      throw new Error("The form assistant returned an invalid proposal.");
    }
    return payload.action === "propose"
      ? { action: "propose", message, field_id: fieldId, value }
      : { action: "confirmed", message, field_id: fieldId, value };
  }

  return { action: payload.action, message, field_id: fieldId };
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
    pendingProposal = { field_id: pendingField.id, value: pendingValue };
  }

  const state: ConversationState = {
    phase: payload.phase,
    active_field_id: activeFieldId,
    pending_proposal: pendingProposal,
  };
  const phaseNeedsActiveField = [
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
    "field_confirmed",
    "field_skipped",
  ].includes(state.phase);
  if (
    (phaseNeedsActiveField && state.active_field_id === null) ||
    (["asking", "form_complete"].includes(state.phase) &&
      state.active_field_id !== null) ||
    (state.phase === "awaiting_confirmation" &&
      (state.pending_proposal === null ||
        state.pending_proposal.field_id !== state.active_field_id)) ||
    (state.phase !== "awaiting_confirmation" &&
      state.pending_proposal !== null)
  ) {
    throw new Error("The API returned an invalid conversation state.");
  }
  return state;
}

function validateAgentResponseState(
  action: AgentAction,
  state: ConversationState,
  requestFields: AgentRequestField[],
) {
  const isResolutionAction =
    action.action === "confirmed" || action.action === "skip";
  const resolutionField =
    action.field_id === null
      ? undefined
      : findAgentField(requestFields, action.field_id);
  const resolutionFieldWasUnanswered =
    resolutionField?.status === "unanswered";
  const expectedNextField = isResolutionAction
    ? requestFields.find(
        (field) =>
          field.status === "unanswered" && field.id !== action.field_id,
      )
    : undefined;
  const progressedToNextField =
    isResolutionAction &&
    resolutionFieldWasUnanswered &&
    expectedNextField !== undefined &&
    state.phase === "awaiting_answer" &&
    state.active_field_id === expectedNextField.id;
  const completedForm =
    isResolutionAction &&
    resolutionFieldWasUnanswered &&
    expectedNextField === undefined &&
    state.phase === "form_complete" &&
    state.active_field_id === null;

  if (!isResolutionAction && action.field_id !== state.active_field_id) {
    throw new Error("The assistant response and conversation state disagree.");
  }

  const validPhase =
    (action.action === "propose" &&
      state.phase === "awaiting_confirmation" &&
      state.pending_proposal?.field_id === action.field_id &&
      state.pending_proposal.value === action.value) ||
    (action.action === "confirmed" &&
      (progressedToNextField || completedForm)) ||
    (action.action === "rejected" && state.phase === "awaiting_answer") ||
    (action.action === "skip" &&
      (progressedToNextField || completedForm)) ||
    (action.action === "explain" && state.phase === "awaiting_answer") ||
    (action.action === "clarify" &&
      ["awaiting_clarification", "awaiting_confirmation"].includes(
        state.phase,
      )) ||
    (action.action === "next" &&
      ((action.field_id === null && state.phase === "form_complete") ||
        (action.field_id !== null && state.phase === "awaiting_answer")));
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

function isAgentActionKind(value: unknown): value is AgentActionKind {
  return [
    "explain",
    "clarify",
    "propose",
    "skip",
    "next",
    "confirmed",
    "rejected",
  ].includes(value as AgentActionKind);
}

function isConversationPhase(value: unknown): value is ConversationPhase {
  return [
    "asking",
    "awaiting_answer",
    "awaiting_clarification",
    "awaiting_confirmation",
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

function getAgentActionLabel(action?: AgentActionKind): string {
  const labels: Record<AgentActionKind, string> = {
    explain: "Explanation",
    clarify: "Clarification",
    propose: "Proposal",
    skip: "Skipped",
    next: "Next field",
    confirmed: "Confirmed",
    rejected: "Rejected",
  };

  return action ? labels[action] : "Form assistant";
}

function createInitialConversationState(): ConversationState {
  return {
    phase: "asking",
    active_field_id: null,
    pending_proposal: null,
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
