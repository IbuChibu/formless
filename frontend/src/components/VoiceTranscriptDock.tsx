import type { VoiceAssistantControls } from "../useVoiceAssistant";
import type {
  VoiceInterviewControls,
  VoiceInterviewStatus,
} from "../useVoiceInterview";

type VoiceTranscriptDockProps = {
  agentIsBusy: boolean;
  hasPendingProposal: boolean;
  interview: VoiceInterviewControls;
  voice: VoiceAssistantControls;
};

export default function VoiceTranscriptDock({
  agentIsBusy,
  hasPendingProposal,
  interview,
  voice,
}: VoiceTranscriptDockProps) {
  const isCapturing = isVoiceCapturing(interview.status);
  const transcriptIsEditable =
    Boolean(voice.transcript) && interview.status !== "listening";
  const canSubmitTranscript =
    transcriptIsEditable &&
    !agentIsBusy &&
    interview.isActive &&
    !isCapturing;

  if (!voice.transcript && !isCapturing) {
    return null;
  }

  return (
    <section
      className={`assistant-live-transcript ${
        isCapturing ? "capturing" : "captured"
      }`}
      aria-label="Live voice transcript"
    >
      <label htmlFor="voice-transcript">
        <span>
          <i aria-hidden="true" />
          {isCapturing
            ? voice.transcriptFinality === "interim"
              ? "Listening · what I hear"
              : "Listening"
            : "What I heard"}
        </span>
        <textarea
          id="voice-transcript"
          value={voice.transcript}
          readOnly={!transcriptIsEditable}
          placeholder="Your words will appear here as you speak…"
          onChange={(event) => voice.setTranscript(event.target.value)}
        />
      </label>

      {canSubmitTranscript ? (
        <div className="assistant-live-transcript-actions">
          <button
            type="button"
            onClick={() =>
              interview.submitEditedTranscript(hasPendingProposal)
            }
          >
            {hasPendingProposal ? "Use correction" : "Send edit"}
          </button>
          <button type="button" onClick={voice.clearTranscript}>
            Clear
          </button>
        </div>
      ) : null}
    </section>
  );
}

function isVoiceCapturing(status: VoiceInterviewStatus): boolean {
  return ["requesting_permission", "listening", "processing"].includes(
    status,
  );
}
