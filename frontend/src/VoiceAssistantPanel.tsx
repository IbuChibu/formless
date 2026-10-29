import type {
  VoiceAssistantControls,
  VoiceInterruptionStatus,
} from "./useVoiceAssistant";
import type {
  VoiceInterviewControls,
  VoiceInterviewStatus,
} from "./useVoiceInterview";

type VoiceAssistantPanelProps = {
  voice: VoiceAssistantControls;
  interview: VoiceInterviewControls;
  agentIsBusy: boolean;
  hasPendingProposal: boolean;
  voicePreferred?: boolean;
};

export default function VoiceAssistantPanel({
  voice,
  interview,
  agentIsBusy,
  hasPendingProposal,
  voicePreferred = false,
}: VoiceAssistantPanelProps) {
  const statusCopy = getInterviewStatusCopy(
    interview.status,
    voice.inputError,
    hasPendingProposal,
    voice.interruptionStatus,
    voice.interruptionError,
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
      className={`voice-assistant-panel ${interview.status}${
        voicePreferred ? " preferred" : ""
      }`}
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
            <span>
              {voicePreferred
                ? "Your preferred way to answer — it starts only when you choose"
                : "The assistant asks, listens, and checks each answer"}
            </span>
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
        {["inactive", "ended"].includes(interview.status) ? (
          <button
            className="voice-primary-button"
            type="button"
            disabled={agentIsBusy || !voice.inputSupported}
            onClick={interview.startInterview}
          >
            <span aria-hidden="true">●</span>
            {interview.status === "ended"
              ? "Start another conversation"
              : "Start conversation"}
          </button>
        ) : ["paused", "muted"].includes(interview.status) ? (
          <>
            <button
              className="voice-primary-button"
              type="button"
              disabled={agentIsBusy || !voice.inputSupported}
              onClick={
                interview.status === "muted"
                  ? interview.unmuteInterview
                  : interview.resumeInterview
              }
            >
              {interview.status === "muted"
                ? "Unmute and continue"
                : "Resume conversation"}
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
          <span>
            {isCapturing
              ? voice.transcriptFinality === "interim"
                ? "What I hear · interim"
                : "What I hear"
              : voice.transcriptFinality === "final"
                ? "What I heard · final"
                : "What I heard"}
          </span>
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
            Tell the assistant naturally whether the answer is right, wrong,
            needs changing, or should be read back. The visible proposal
            controls remain available.
          </span>
        </div>
      ) : (
        <small className="voice-confirmation-note">
          After you start, Formless automatically listens again after each
          reply and keeps the microphone available only for this visible
          session. You can interrupt by talking, or use Mute, Pause, End,
          Answer now, and typing at any time. Formless does not retain audio or
          speech metadata.
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
      {interview.isActive ? (
        <button
          className="voice-secondary-button"
          type="button"
          onClick={interview.muteInterview}
        >
          Mute
        </button>
      ) : null}
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
  if (status === "recovering") {
    return "Reopening listening";
  }
  if (status === "interrupted") {
    return "Opening your turn";
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
  interruptionStatus: VoiceInterruptionStatus,
  interruptionError: string | null,
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
      label:
        interruptionStatus === "armed"
          ? "Speak when ready"
          : interruptionStatus === "arming"
            ? "Preparing microphone"
            : "Assistant speaking",
      detail:
        interruptionStatus === "armed"
          ? "Start talking whenever you are ready. The assistant will stop and open your one-turn transcript."
          : interruptionStatus === "arming"
            ? "Hands-free interruption is getting ready. You can still choose Answer now immediately."
            : interruptionStatus === "error"
              ? (interruptionError ??
                "Hands-free interruption could not start. Use Answer now or type your reply.")
              : interruptionStatus === "unsupported"
                ? "Hands-free interruption is unavailable here. Use Answer now or type your reply."
                : "Listen to the question, or choose Answer now to interrupt and start your turn.",
    },
    interrupted: {
      label: "Listening to you",
      detail:
        "The assistant stopped. Your microphone is moving directly into the same Deepgram turn so you can continue speaking.",
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
        "Deepgram is finalizing the visible transcript. No form value has changed.",
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
    recovering: {
      label: "Still listening",
      detail:
        "No answer was sent. Formless is reopening the microphone automatically and your form is unchanged.",
    },
    muted: {
      label: "Muted",
      detail:
        "The microphone and spoken reply are off. Your form and conversation are unchanged.",
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
    ended: {
      label: "Conversation ended",
      detail:
        "Microphone access and spoken replies are off. You can keep typing or start another voice conversation.",
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
        "Streaming voice input is unavailable in this browser or connection. The typed interview and proposal controls still work.",
    },
  };

  return copy[status];
}
