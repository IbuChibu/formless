import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import VoiceAssistantPanel from "./VoiceAssistantPanel";
import useVoiceAssistant from "./useVoiceAssistant";
import useVoiceInterview from "./useVoiceInterview";
import ActiveQuestionCard from "./components/ActiveQuestionCard";
import AppHeader from "./components/AppHeader";
import ConversationTranscript from "./components/ConversationTranscript";
import DocumentWorkspace from "./components/DocumentWorkspace";
import FormReviewPanel from "./components/FormReviewPanel";
import ManualFieldsDrawer from "./components/ManualFieldsDrawer";
import ProposalReview from "./components/ProposalReview";
import SupportPreferencesPanel from "./components/SupportPreferencesPanel";
import UploadLanding from "./components/UploadLanding";
import {
  createDefaultAssistancePreferences,
  hasAssistancePreferences,
} from "./assistancePreferences";
import { parseAgentResponse } from "./agentResponse";
import {
  apiBaseUrl,
  getErrorMessage,
  isAbortError,
  isValidFormContext,
  readApiError,
} from "./api";
import {
  agentRequestNeedsExternalGuidance,
  buildAgentRequestFields,
  countReviewStatuses,
  createInitialConversationState,
  getInitialFieldValue,
  getLatestAssistantTurn,
  getQuickAnswerOptions,
  getReviewFieldStatus,
  groupFieldsByPage,
  hasInitialConfirmedValue,
  humanizeFieldId,
  isAgentValueCompatible,
  isDirectlyEditableField,
  isExplainableField,
  isManuallyConfirmedValue,
} from "./formFieldState";
import type {
  AgentActivity,
  AgentEvent,
  AgentRequest,
  AgentStatus,
  AssistancePreferences,
  ConnectionStatus,
  ConversationMessage,
  ConversationState,
  ExtractionStatus,
  FieldValue,
  FormContext,
  HealthResponse,
  MobileWorkspaceView,
  PdfExtractionResponse,
  PdfField,
  PreviewStatus,
  ProposalAgentEffect,
  SupportIntroductionStatus,
} from "./formTypes";

const previewDebounceMs = 600;
const maxAgentHistoryMessages = 8;
function App() {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("checking");
  const [connectionCheckNonce, setConnectionCheckNonce] = useState(0);
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
  const [previewRetryNonce, setPreviewRetryNonce] = useState(0);
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
  const [reviewPanelOpen, setReviewPanelOpen] = useState(false);
  const [directEditFieldId, setDirectEditFieldId] = useState<string | null>(
    null,
  );
  const [directEditValue, setDirectEditValue] = useState<FieldValue>("");
  const [showFullTranscript, setShowFullTranscript] = useState(false);
  const [mobileWorkspaceView, setMobileWorkspaceView] =
    useState<MobileWorkspaceView>("assistant");
  const [assistancePreferences, setAssistancePreferences] =
    useState<AssistancePreferences>(createDefaultAssistancePreferences());
  const [supportIntroductionStatus, setSupportIntroductionStatus] =
    useState<SupportIntroductionStatus>("pending");
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
      setConnectionStatus("checking");
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
  }, [connectionCheckNonce]);

  useEffect(() => {
    if (!selectedFile || extractionStatus !== "ready") {
      return;
    }

    if (Object.keys(changedValues).length === 0) {
      if (filledUrlRef.current) {
        URL.revokeObjectURL(filledUrlRef.current);
        filledUrlRef.current = null;
      }
      setPreviewUrl(originalUrlRef.current);
      setDownloadUrl(null);
      setPreviewError(null);
      setPreviewStatus("idle");
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
  }, [changedValues, extractionStatus, previewRetryNonce, selectedFile]);

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

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.type !== "application/pdf") {
      setExtractionError("Choose a PDF file to continue.");
      setExtractionStatus("error");
      return;
    }

    void extractPdfFile(file);
  }

  async function extractPdfFile(file: File) {
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
    setReviewPanelOpen(false);
    setDirectEditFieldId(null);
    setDirectEditValue("");
    setShowFullTranscript(false);
    setMobileWorkspaceView("assistant");
    setAssistancePreferences(createDefaultAssistancePreferences());
    setSupportIntroductionStatus("pending");
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

  function retryExtraction() {
    if (selectedFile && extractionStatus !== "loading") {
      void extractPdfFile(selectedFile);
    }
  }

  function updateField(fieldId: string, value: FieldValue) {
    const field = fields.find((candidate) => candidate.id === fieldId);
    if (!field || !field.supported || !field.editable) {
      return;
    }

    const isConfirmed = isManuallyConfirmedValue(field, value);

    writeFieldValue(fieldId, value, isConfirmed);

    const replacesActiveAgentValue =
      agentConversationState.active_field_id === fieldId ||
      agentConversationState.pending_proposal?.field_id === fieldId;
    setAgentConversationState((current) => {
      const rememberedCandidates = current.remembered_candidates.filter(
        (candidate) => candidate.field_id !== fieldId,
      );
      if (
        current.active_field_id === fieldId ||
        current.pending_proposal?.field_id === fieldId
      ) {
        return {
          phase: isConfirmed ? "field_confirmed" : "awaiting_answer",
          active_field_id: fieldId,
          pending_proposal: null,
          remembered_candidates: rememberedCandidates,
        };
      }
      return rememberedCandidates.length ===
        current.remembered_candidates.length
        ? current
        : { ...current, remembered_candidates: rememberedCandidates };
    });
    if (replacesActiveAgentValue) {
      resetProposalEditor();
    }
  }

  function openDirectEditor(fieldId: string) {
    const field = fields.find((candidate) => candidate.id === fieldId);
    if (!field || !isDirectlyEditableField(field)) {
      return;
    }

    setDirectEditFieldId(fieldId);
    setDirectEditValue(
      formValues[fieldId] ?? getInitialFieldValue(field),
    );
    setMobileWorkspaceView("form");
  }

  function closeDirectEditor() {
    setDirectEditFieldId(null);
    setDirectEditValue("");
    window.requestAnimationFrame(() => {
      document.getElementById("document-workspace")?.focus();
    });
  }

  function closeReviewPanel() {
    setReviewPanelOpen(false);
    window.requestAnimationFrame(() => {
      document.getElementById("open-form-review")?.focus();
    });
  }

  function saveDirectEdit() {
    if (!directEditFieldId) {
      return;
    }

    const field = fields.find(
      (candidate) => candidate.id === directEditFieldId,
    );
    if (!field || !isManuallyConfirmedValue(field, directEditValue)) {
      return;
    }

    updateField(field.id, directEditValue);
    closeDirectEditor();
  }

  function clearDirectEdit() {
    if (!directEditFieldId) {
      return;
    }

    const field = fields.find(
      (candidate) => candidate.id === directEditFieldId,
    );
    if (!field || !isDirectlyEditableField(field)) {
      return;
    }

    updateField(field.id, field.type === "checkbox" ? false : "");
    closeDirectEditor();
  }

  function writeFieldValue(
    fieldId: string,
    value: FieldValue,
    isConfirmed: boolean,
  ) {
    setFormValues((current) => ({ ...current, [fieldId]: value }));
    setChangedValues((current) => {
      const next = { ...current };
      if (isConfirmed) {
        next[fieldId] = value;
      } else {
        delete next[fieldId];
      }
      return next;
    });
    if (directEditFieldId === fieldId) {
      setDirectEditValue(value);
    }
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

      if (effect.effect === "assistance_preferences_updated") {
        setAssistancePreferences(effect.preferences);
        setSupportIntroductionStatus(effect.introduction_status);
      } else if (
        request.conversation_state.phase === "support_setup" &&
        conversationState.phase !== "support_setup"
      ) {
        setSupportIntroductionStatus("skipped");
      }

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
        setChangedValues((current) => {
          const next = { ...current };
          delete next[effect.field_id];
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
      assistance_preferences: assistancePreferences,
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

  function advanceAgent() {
    if (
      agentConversationState.phase === "support_setup" &&
      supportIntroductionStatus === "skipped"
    ) {
      sendAgentEvent({ type: "message", content: "Just start the form." });
      return;
    }
    sendAgentEvent({ type: "advance" });
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
  const reviewItems = fields.filter(isDirectlyEditableField).map((field) => ({
    field,
    status: getReviewFieldStatus(
      field.id,
      pendingProposal?.field_id ?? null,
      confirmedFieldIds,
      skippedFieldIds,
    ),
  }));
  const reviewCounts = countReviewStatuses(reviewItems);
  const directEditField = fields.find(
    (field) => field.id === directEditFieldId,
  );
  const canSaveDirectEdit = Boolean(
    directEditField &&
      isManuallyConfirmedValue(directEditField, directEditValue),
  );
  const pdfNavigationFieldId =
    directEditFieldId ?? pendingProposal?.field_id ?? agentActiveFieldId;
  const pdfViewerFields = reviewItems.map(({ field, status }) => ({
    id: field.id,
    label: field.label || humanizeFieldId(field.id),
    question: field.question,
    supported: field.supported,
    editable: field.editable,
    page: field.page,
    widgets: field.widgets,
    status,
  }));
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
    ["support_setup", "asking"].includes(agentConversationState.phase) &&
    agentMessages.length === 0;
  const canResumeAgent = ["field_confirmed", "field_skipped"].includes(
    agentConversationState.phase,
  );
  const canSendAgentMessage = [
    "support_setup",
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
    activeField: activeAgentField
      ? {
          id: activeAgentField.id,
          label: activeAgentField.label,
          question: activeAgentField.question,
          type: activeAgentField.type,
        }
      : null,
    activeQuestion: activeAgentQuestion,
    hasPendingProposal: pendingProposal !== null,
    isFormComplete: agentConversationState.phase === "form_complete",
    onAdvance: advanceAgent,
    onSendMessage: sendAgentMessage,
  });

  return (
    <div className={`app-shell${selectedFile ? " document-loaded" : ""}`}>
      <AppHeader
        completedFilename={completedFilename}
        connectionCopy={connectionCopy}
        connectionStatus={connectionStatus}
        currentFieldCount={currentAgentFields.length}
        downloadUrl={downloadUrl}
        extractionStatus={extractionStatus}
        onFileSelection={handleFileSelection}
        onOpenReview={() => {
          setReviewPanelOpen(true);
          setMobileWorkspaceView("assistant");
        }}
        onRetryConnection={() =>
          setConnectionCheckNonce((current) => current + 1)
        }
        reviewItemCount={reviewItems.length}
        reviewedFieldCount={reviewedAgentFieldCount}
        selectedFile={selectedFile}
      />

      <main
        className={`app-main${selectedFile ? " workspace-main" : " landing-main"}`}
      >
        {extractionError ? (
          <div className="error-banner" role="alert">
            <div>
              <strong>Could not read this form.</strong>
              <span>{extractionError}</span>
            </div>
            {selectedFile && extractionStatus === "error" ? (
              <button type="button" onClick={retryExtraction}>
                Retry field extraction
              </button>
            ) : null}
          </div>
        ) : null}

        {!selectedFile ? (
          <UploadLanding onFileSelection={handleFileSelection} />
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
            <DocumentWorkspace
              activeFieldId={pdfNavigationFieldId}
              canSaveDirectEdit={canSaveDirectEdit}
              directEditField={directEditField}
              directEditFieldId={directEditFieldId}
              directEditValue={directEditValue}
              fields={pdfViewerFields}
              isMobileActive={mobileWorkspaceView === "form"}
              originalUrlKey={originalUrlRef.current ?? selectedFile.name}
              previewCopy={previewCopy}
              previewError={previewError}
              previewStatus={previewStatus}
              previewUrl={previewUrl}
              selectedFileName={selectedFile.name}
              onChangeDirectEditValue={setDirectEditValue}
              onClearDirectEdit={clearDirectEdit}
              onCloseDirectEditor={closeDirectEditor}
              onRetryPreview={() =>
                setPreviewRetryNonce((current) => current + 1)
              }
              onSaveDirectEdit={saveDirectEdit}
              onSelectField={openDirectEditor}
            />

            <aside
              className={`panel fields-panel assistant-workspace mobile-workspace-view${
                mobileWorkspaceView === "assistant"
                  ? " mobile-view-active"
                  : ""
              }`}
              id="assistant-workspace"
              data-input-preference={assistancePreferences.interaction_mode}
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

              {canUseAgent ? (
                <SupportPreferencesPanel
                  disabled={agentStatus === "loading"}
                  preferences={assistancePreferences}
                  status={supportIntroductionStatus}
                  onSave={(preferences) => {
                    setAssistancePreferences(preferences);
                    setSupportIntroductionStatus(
                      hasAssistancePreferences(preferences)
                        ? "saved"
                        : "skipped",
                    );
                  }}
                  onSkip={() => {
                    setAssistancePreferences(
                      createDefaultAssistancePreferences(),
                    );
                    setSupportIntroductionStatus("skipped");
                  }}
                />
              ) : null}

              {reviewPanelOpen ? (
                <FormReviewPanel
                  counts={reviewCounts}
                  formValues={formValues}
                  items={reviewItems}
                  proposedFieldId={pendingProposal?.field_id ?? null}
                  proposedValue={pendingProposal?.value}
                  onClose={closeReviewPanel}
                  onSelectField={(fieldId) => {
                    setReviewPanelOpen(false);
                    openDirectEditor(fieldId);
                  }}
                />
              ) : null}

              {extractionStatus === "loading" ? (
                <div className="workspace-status">
                  <div className="loading-state" aria-live="polite">
                    <span className="spinner" aria-hidden="true" />
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
                    <p>
                      This PDF remains available in the preview, but it does
                      not expose AcroForm fields that Formless can edit. Use
                      Change PDF to choose another fillable document.
                    </p>
                  </div>
                </div>
              ) : null}

              {extractionStatus === "error" ? (
                <div className="workspace-status">
                  <div className="message-state" role="alert">
                    <strong>Fields unavailable</strong>
                    <p>
                      The original PDF is still available in the preview.
                      Use Retry field extraction above or Change PDF without
                      losing it.
                    </p>
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
                    voicePreferred={
                      assistancePreferences.interaction_mode === "voice"
                    }
                  />
                ) : null}

                {activeAgentField && activeAgentQuestion ? (
                  <ActiveQuestionCard
                    agentStatus={agentStatus}
                    canAnswer={canAnswerActiveQuestion}
                    field={activeAgentField}
                    fieldIndex={activeAgentFieldIndex}
                    phase={agentConversationState.phase}
                    question={activeAgentQuestion}
                    quickAnswers={activeQuickAnswers}
                    section={activeAgentSection}
                    totalFields={currentAgentFields.length}
                    transcriptLength={agentMessages.length}
                    onAskForGuidance={() =>
                      sendAgentMessage(
                        "Check official guidance for this question.",
                      )
                    }
                    onAskForPlainLanguage={() =>
                      sendAgentMessage(
                        "Explain this question in plain language.",
                      )
                    }
                    onQuickAnswer={sendAgentMessage}
                    onSkip={(fieldId) =>
                      sendAgentEvent({ type: "skip", field_id: fieldId })
                    }
                  />
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
                  <ConversationTranscript
                    agentStatus={agentStatus}
                    fields={fields}
                    messages={agentMessages}
                    showFullTranscript={showFullTranscript}
                    visibleMessages={visibleAgentMessages}
                    onRetryGuidance={(request) => void requestAgent(request)}
                    onToggleFullTranscript={() =>
                      setShowFullTranscript((current) => !current)
                    }
                  />
                ) : null}

                {pendingProposal && pendingProposalField ? (
                  <ProposalReview
                    agentStatus={agentStatus}
                    canApplyEditedProposal={canApplyEditedProposal}
                    canUseOriginalProposal={canUseOriginalProposal}
                    details={activeProposalDetails}
                    field={pendingProposalField}
                    isEditing={isEditingProposal}
                    isReplacement={isReplacementPending}
                    pendingProposal={pendingProposal}
                    proposalEditValue={proposalEditValue}
                    onCancelCorrection={() =>
                      sendAgentEvent({ type: "cancel_correction" })
                    }
                    onCancelEdit={() => {
                      setProposalEditValue(pendingProposal.value);
                      setIsEditingProposal(false);
                    }}
                    onChangeEditValue={setProposalEditValue}
                    onConfirm={confirmPendingProposal}
                    onEdit={() => {
                      setProposalEditValue(pendingProposal.value);
                      setIsEditingProposal(true);
                    }}
                    onReject={rejectPendingProposal}
                    onSkip={skipPendingProposal}
                    onUseOriginal={useOriginalProposal}
                  />
                ) : null}

                {agentStatus === "loading" ? (
                  <div
                    className="ai-explanation-state"
                    aria-live="polite"
                    role="status"
                  >
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
                    onClick={advanceAgent}
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
                        onClick={() => setReviewPanelOpen(true)}
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
                  data-input-preferred={
                    assistancePreferences.interaction_mode === "typing"
                  }
                  onSubmit={submitAgentMessage}
                >
                  <label htmlFor="agent-message">
                    {agentConversationState.phase === "support_setup"
                      ? "Tell me what would make this form easier"
                      : activeAgentField
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
                        agentConversationState.phase === "support_setup"
                          ? "For example: Use simpler words and go slowly"
                          : activeAgentField
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

              <ManualFieldsDrawer
                activeFieldId={agentActiveFieldId}
                agentFields={currentAgentFields}
                agentStatus={agentStatus}
                fieldCount={fields.length}
                fieldGroups={fieldGroups}
                formValues={formValues}
                isOpen={manualDrawerOpen}
                isReady={extractionStatus === "ready"}
                hasPendingProposal={pendingProposal !== null}
                onAskForExplanation={(fieldId, message) =>
                  sendAgentEvent(
                    {
                      type: "focus_field",
                      field_id: fieldId,
                      content: message,
                    },
                    message,
                  )
                }
                onChangeField={updateField}
                onToggle={() => setManualDrawerOpen((current) => !current)}
              />
            </aside>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
