import { getQuestionStatusLabel } from "../formFieldState";
import type {
  AgentStatus,
  ConversationPhase,
  PdfField,
} from "../formTypes";

type QuickAnswer = { label: string; message: string; value: string };

type ActiveQuestionCardProps = {
  agentStatus: AgentStatus;
  canAnswer: boolean;
  field: PdfField;
  fieldIndex: number;
  phase: ConversationPhase;
  question: string;
  quickAnswers: QuickAnswer[];
  section: string | null | undefined;
  totalFields: number;
  transcriptLength: number;
  onAskForGuidance: () => void;
  onAskForPlainLanguage: () => void;
  onQuickAnswer: (message: string) => void;
  onSkip: (fieldId: string) => void;
};

export default function ActiveQuestionCard({
  agentStatus,
  canAnswer,
  field,
  fieldIndex,
  phase,
  question,
  quickAnswers,
  section,
  totalFields,
  transcriptLength,
  onAskForGuidance,
  onAskForPlainLanguage,
  onQuickAnswer,
  onSkip,
}: ActiveQuestionCardProps) {
  return (
    <section
      className={`guided-question-card ${phase}`}
      aria-labelledby="active-question-heading"
    >
      <div className="guided-question-meta">
        <div>
          <span>{section || "Guided interview"}</span>
          {field.page ? <span>Page {field.page}</span> : null}
        </div>
        {fieldIndex >= 0 ? (
          <strong>
            Question {fieldIndex + 1} of {totalFields}
          </strong>
        ) : null}
      </div>

      <div className="guided-question-copy">
        <span>{getQuestionStatusLabel(phase)}</span>
        <h3 id="active-question-heading">{question}</h3>
        {field.help_text ? <p>{field.help_text}</p> : null}
      </div>

      {canAnswer && quickAnswers.length > 0 ? (
        <fieldset className="agent-quick-answers">
          <legend>Quick answers</legend>
          {quickAnswers.length <= 6 ? (
            <div>
              {quickAnswers.map((answer) => (
                <button
                  key={answer.value}
                  type="button"
                  disabled={agentStatus === "loading"}
                  onClick={() => onQuickAnswer(answer.message)}
                >
                  {answer.label}
                </button>
              ))}
            </div>
          ) : (
            <label>
              <span>Choose an available answer</span>
              <select
                key={`${field.id}-${transcriptLength}`}
                defaultValue=""
                disabled={agentStatus === "loading"}
                onChange={(event) => {
                  if (event.target.value) {
                    onQuickAnswer(event.target.value);
                  }
                }}
              >
                <option value="" disabled>
                  Select an option
                </option>
                {quickAnswers.map((answer) => (
                  <option key={answer.value} value={answer.message}>
                    {answer.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <small>You can still type your answer below.</small>
        </fieldset>
      ) : null}

      {canAnswer ? (
        <div
          className="guided-question-actions"
          aria-label="Help with this question"
        >
          <button
            type="button"
            disabled={agentStatus === "loading"}
            onClick={onAskForPlainLanguage}
          >
            Explain this
          </button>
          <button
            type="button"
            disabled={agentStatus === "loading"}
            onClick={onAskForGuidance}
          >
            Check guidance
          </button>
          <button
            type="button"
            disabled={agentStatus === "loading"}
            onClick={() => onSkip(field.id)}
          >
            Skip for now
          </button>
        </div>
      ) : null}
    </section>
  );
}
