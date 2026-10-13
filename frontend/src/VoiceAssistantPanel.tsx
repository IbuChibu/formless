import type { VoiceAssistantControls } from "./useVoiceAssistant";
import type {
  VoiceInterviewControls,
  VoiceInterviewStatus,
} from "./useVoiceInterview";

type VoiceAssistantPanelProps = {
  voice: VoiceAssistantControls;
  interview: VoiceInterviewControls;
  agentIsBusy: boolean;
  hasPendingProposal: boolean;
};

export default function VoiceAssistantPanel({
  voice,
  interview,
  agentIsBusy,
  hasPendingProposal,
}: VoiceAssistantPanelProps) {
  const statusCopy = getInterviewStatusCopy(
    interview.status,
    voice.inputError,
    hasPendingProposal,
  );
  const isCapturing = [
    "requesting_permission",
    "listening",
    "processing",
  ].includes(interview.status);
  const transcriptIsEditable =
    Boolean(voice.transcript) && interview.status !== "listening";
  const canSubmitTranscript =
    transcriptIsEditable &&
    !agentIsBusy &&
    interview.isActive &&
    !isCapturing;

  return (
    <section
      className={`voice-assistant-panel ${interview.status}`}
      aria-labelledby="voice-assistant-heading"
    >
      <div className="voice-assistant-heading">
        <div>
          <span className="voice-mark" aria-hidden="true">
            <span />
          </span>
          <div>
            <strong id="voice-assistant-heading">
              Talk through this form
            </strong>
            <span>The assistant asks, listens, and checks each answer</span>
          </div>
        </div>
        <span className="voice-status-label">{statusCopy.label}</span>
      </div>

      <p
        className="voice-status-copy"
        role={interview.status === "error" ? "alert" : "status"}
        aria-live="polite"
      >
        {statusCopy.detail}
      </p>

      <div className="voice-conversation-actions">
        {interview.status === "inactive" ? (
          <button
            className="voice-primary-button"
            type="button"
            disabled={agentIsBusy || !voice.inputSupported}
            onClick={interview.startInterview}
          >
            <span aria-hidden="true">●</span>
            Start conversation
          </button>
        ) : interview.status === "paused" ? (
          <>
            <button
              className="voice-primary-button"
              type="button"
              disabled={agentIsBusy || !voice.inputSupported}
              onClick={interview.resumeInterview}
            >
              Resume conversation
            </button>
            <button
              className="voice-secondary-button"
              type="button"
              onClick={interview.endInterview}
            >
              End conversation
            </button>
          </>
        ) : interview.status === "assistant_speaking" ? (
          <>
            <button
              className="voice-primary-button"
              type="button"
              onClick={interview.interruptAndListen}
            >
              <span aria-hidden="true">●</span>
              Answer now
            </button>
            <SessionStopButtons interview={interview} />
          </>
        ) : interview.status === "listening" ? (
          <>
            <button
              className="voice-primary-button listening"
              type="button"
              onClick={voice.stopListening}
            >
              <span aria-hidden="true">■</span>
              Finish answer
            </button>
            <SessionStopButtons interview={interview} />
          </>
        ) : interview.status === "error" ? (
          <>
            <button
              className="voice-primary-button"
              type="button"
              disabled={agentIsBusy || !voice.inputSupported}
              onClick={interview.retryListening}
            >
              Try listening again
            </button>
            <SessionStopButtons interview={interview} />
          </>
        ) : interview.status === "complete" ? (
          <>
            <button
              className="voice-primary-button"
              type="button"
              disabled={agentIsBusy || !voice.inputSupported}
              onClick={interview.retryListening}
            >
              Ask a review question
            </button>
            <SessionStopButtons interview={interview} />
          </>
        ) : interview.status === "unsupported" ? (
          <button
            className="voice-secondary-button"
            type="button"
            onClick={interview.endInterview}
          >
            Keep typing instead
          </button>
        ) : (
          <>
            <button className="voice-primary-button" type="button" disabled>
              <span className="voice-pulse" aria-hidden="true" />
              {getBusyButtonLabel(interview.status, hasPendingProposal)}
            </button>
            <SessionStopButtons interview={interview} />
          </>
        )}
      </div>

      {voice.transcript || isCapturing ? (
        <label className="voice-transcript" htmlFor="voice-transcript">
          <span>{isCapturing ? "What I hear" : "What I heard"}</span>
          <textarea
            id="voice-transcript"
            value={voice.transcript}
            readOnly={!transcriptIsEditable}
            placeholder={
              isCapturing
                ? "Your words will appear here…"
                : "The recognized answer will stay visible here"
            }
            onChange={(event) => voice.setTranscript(event.target.value)}
          />
        </label>
      ) : null}

      {canSubmitTranscript ? (
        <div className="voice-transcript-actions">
          <button
            className="primary"
            type="button"
            onClick={() =>
              interview.submitEditedTranscript(hasPendingProposal)
            }
          >
            {hasPendingProposal
              ? "Use corrected transcript"
              : "Send edited transcript"}
          </button>
          <button type="button" onClick={voice.clearTranscript}>
            Clear transcript
          </button>
        </div>
      ) : null}

      {hasPendingProposal ? (
        <div className="voice-confirmation-note">
          <strong>Confirmation needed</strong>
          <span>
            Say “confirm that”, “put that in”, “no”, or “skip this”. The
            visible proposal controls remain available.
          </span>
        </div>
      ) : (
        <small className="voice-confirmation-note">
          The microphone listens for one turn at a time. Pause or end the
          conversation whenever you want; typing always remains available.
        </small>
      )}

      {!voice.outputSupported ? (
        <p className="voice-output-error" role="status">
          Spoken replies are unavailable in this browser. Read the visible
          question, or keep using the microphone and typed controls.
        </p>
      ) : voice.outputError ? (
        <p className="voice-output-error" role="alert">
          {voice.outputError}
        </p>
      ) : null}
    </section>
  );
}

function SessionStopButtons({
  interview,
}: {
  interview: VoiceInterviewControls;
}) {
  return (
    <>
      <button
        className="voice-secondary-button"
        type="button"
        onClick={interview.pauseInterview}
      >
        Pause
      </button>
      <button
        className="voice-secondary-button quiet"
        type="button"
        onClick={interview.endInterview}
      >
        End
      </button>
    </>
  );
}

function getBusyButtonLabel(
  status: VoiceInterviewStatus,
  hasPendingProposal: boolean,
): string {
  if (status === "requesting_permission") {
    return "Waiting for microphone";
  }
  if (status === "processing") {
    return "Preparing your words";
  }
  if (status === "waiting_agent") {
    return "Thinking about your answer";
  }
  if (status === "awaiting_confirmation" || hasPendingProposal) {
    return "Waiting for your decision";
  }
  return "Starting conversation";
}

function getInterviewStatusCopy(
  status: VoiceInterviewStatus,
  inputError: string | null,
  hasPendingProposal: boolean,
): { label: string; detail: string } {
  const copy: Record<VoiceInterviewStatus, { label: string; detail: string }> = {
    inactive: {
      label: "Ready",
      detail:
        "Start once, then take turns with the assistant as you work through the form.",
    },
    starting: {
      label: "Starting",
      detail:
        "The assistant is getting the current question ready. The microphone is not listening yet.",
    },
    assistant_speaking: {
      label: "Assistant speaking",
      detail:
        "Listen to the question, or choose Answer now to interrupt and start your turn.",
    },
    requesting_permission: {
      label: "Microphone permission",
      detail:
        "Your browser may ask for microphone access. It will listen for this turn only.",
    },
    listening: {
      label: hasPendingProposal ? "Listening for your decision" : "Listening",
      detail: hasPendingProposal
        ? "Confirm, reject, correct, or skip the visible proposal in your own words."
        : "Speak naturally. Pause briefly when you are finished, or choose Finish answer.",
    },
    processing: {
      label: "Preparing transcript",
      detail:
        "The browser is finishing the visible transcript. No form value has changed.",
    },
    waiting_agent: {
      label: "Assistant thinking",
      detail:
        "Your transcript was sent through the same safe Form Agent path as a typed message.",
    },
    awaiting_confirmation: {
      label: "Confirmation needed",
      detail:
        "The proposal is visible and still has not changed the PDF. Say a clear decision or use the buttons.",
    },
    paused: {
      label: "Paused",
      detail:
        "The microphone and spoken reply are stopped. Your form and conversation are unchanged.",
    },
    complete: {
      label: "Interview complete",
      detail:
        "The supported questions are reviewed. You can ask a review question, keep typing, or end the conversation.",
    },
    error: {
      label: "Needs attention",
      detail:
        inputError ??
        "Voice could not continue. Try listening again, or keep using the typed answer box.",
    },
    unsupported: {
      label: "Typing available",
      detail:
        "Voice input is unavailable in this browser or connection. The typed interview and proposal controls still work.",
    },
  };

  return copy[status];
}
