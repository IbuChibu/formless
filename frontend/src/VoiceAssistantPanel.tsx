import type {
  VoiceAssistantControls,
  VoiceInputStatus,
} from "./useVoiceAssistant";

type VoiceAssistantPanelProps = {
  voice: VoiceAssistantControls;
  agentIsBusy: boolean;
  canSendMessage: boolean;
  hasAssistantMessage: boolean;
  hasPendingProposal: boolean;
  onSendTranscript: (transcript: string) => void;
};

export default function VoiceAssistantPanel({
  voice,
  agentIsBusy,
  canSendMessage,
  hasAssistantMessage,
  hasPendingProposal,
  onSendTranscript,
}: VoiceAssistantPanelProps) {
  const inputCopy = getVoiceInputCopy(voice.inputStatus, voice.inputError);
  const inputIsBusy = [
    "requesting_permission",
    "listening",
    "processing",
  ].includes(voice.inputStatus);
  const transcriptCanBeEdited = ["review", "error"].includes(
    voice.inputStatus,
  );

  function submitTranscript() {
    const normalizedTranscript = voice.transcript.trim();
    if (!normalizedTranscript || agentIsBusy || !canSendMessage) {
      return;
    }
    onSendTranscript(normalizedTranscript);
    voice.clearTranscript();
  }

  return (
    <section
      className={`voice-assistant-panel ${voice.inputStatus}`}
      aria-labelledby="voice-assistant-heading"
    >
      <div className="voice-assistant-heading">
        <div>
          <span className="voice-mark" aria-hidden="true">
            ◉
          </span>
          <div>
            <strong id="voice-assistant-heading">Voice answer</strong>
            <span>Review every transcript before sending</span>
          </div>
        </div>
        <span className="voice-status-label">{inputCopy.label}</span>
      </div>

      <p
        className="voice-status-copy"
        role={voice.inputStatus === "error" ? "alert" : "status"}
        aria-live="polite"
      >
        {inputCopy.detail}
      </p>

      {voice.inputStatus !== "unsupported" ? (
        <div className="voice-capture-actions">
          {voice.inputStatus === "listening" ? (
            <button
              className="voice-primary-button listening"
              type="button"
              onClick={voice.stopListening}
            >
              <span aria-hidden="true">■</span>
              Stop listening
            </button>
          ) : inputIsBusy ? (
            <button className="voice-primary-button" type="button" disabled>
              <span className="voice-pulse" aria-hidden="true" />
              {voice.inputStatus === "requesting_permission"
                ? "Waiting for permission"
                : "Preparing transcript"}
            </button>
          ) : (
            <button
              className="voice-primary-button"
              type="button"
              disabled={agentIsBusy || !canSendMessage}
              onClick={voice.startListening}
            >
              <span aria-hidden="true">●</span>
              {voice.inputStatus === "error"
                ? "Try voice again"
                : voice.inputStatus === "review"
                  ? "Record again"
                  : "Start voice answer"}
            </button>
          )}

          {inputIsBusy ? (
            <button
              className="voice-secondary-button"
              type="button"
              onClick={voice.cancelListening}
            >
              Cancel
            </button>
          ) : null}
        </div>
      ) : null}

      {voice.transcript || inputIsBusy ? (
        <label className="voice-transcript" htmlFor="voice-transcript">
          <span>
            {transcriptCanBeEdited
              ? "Review transcript"
              : "Listening transcript"}
          </span>
          <textarea
            id="voice-transcript"
            value={voice.transcript}
            readOnly={!transcriptCanBeEdited}
            placeholder={
              inputIsBusy
                ? "Your words will appear here…"
                : "Review what the browser heard"
            }
            onChange={(event) => voice.setTranscript(event.target.value)}
          />
        </label>
      ) : null}

      {transcriptCanBeEdited && voice.transcript.trim() ? (
        <div className="voice-transcript-actions">
          <button
            className="primary"
            type="button"
            disabled={agentIsBusy || !canSendMessage}
            onClick={submitTranscript}
          >
            Send transcript
          </button>
          <button type="button" onClick={voice.clearTranscript}>
            Clear
          </button>
        </div>
      ) : null}

      <div className="voice-output-controls">
        <label>
          <input
            type="checkbox"
            checked={voice.spokenRepliesEnabled}
            disabled={!voice.outputSupported}
            onChange={(event) =>
              voice.setSpokenRepliesEnabled(event.target.checked)
            }
          />
          <span>
            Read assistant responses aloud
            <small>
              {voice.outputSupported
                ? "Text always remains visible"
                : "Speech output is unavailable in this browser"}
            </small>
          </span>
        </label>
        {voice.outputStatus === "speaking" ? (
          <button type="button" onClick={voice.stopSpeaking}>
            Stop speaking
          </button>
        ) : null}
      </div>

      {voice.outputError ? (
        <p className="voice-output-error" role="alert">
          {voice.outputError}
        </p>
      ) : null}

      {hasPendingProposal ? (
        <small className="voice-confirmation-note">
          Voice does not apply this proposal. Use the visible review controls
          to confirm, edit, reject, or skip it.
        </small>
      ) : hasAssistantMessage && voice.spokenRepliesEnabled ? (
        <small className="voice-confirmation-note">
          New assistant replies will be spoken and will remain in the
          conversation transcript.
        </small>
      ) : null}
    </section>
  );
}

function getVoiceInputCopy(
  status: VoiceInputStatus,
  error: string | null,
): { label: string; detail: string } {
  const copy: Record<VoiceInputStatus, { label: string; detail: string }> = {
    idle: {
      label: "Ready",
      detail:
        "Start the microphone when you are ready. Nothing is sent until you review and send the transcript.",
    },
    requesting_permission: {
      label: "Permission",
      detail:
        "Your browser may ask for microphone access. Allow it only if you want to dictate this answer.",
    },
    listening: {
      label: "Listening",
      detail:
        "Speak naturally, then stop listening. Your words are still only a draft.",
    },
    processing: {
      label: "Processing",
      detail:
        "The browser is preparing your transcript. No form value has changed.",
    },
    review: {
      label: "Review",
      detail:
        "Check and edit the transcript before sending it to the form assistant.",
    },
    error: {
      label: "Voice unavailable",
      detail:
        error ??
        "Voice input could not be completed. Try again or keep typing your answer.",
    },
    unsupported: {
      label: "Typing available",
      detail:
        "Voice input is unavailable in this browser or connection. You can continue with the typed answer box.",
    },
  };

  return copy[status];
}
