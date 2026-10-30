import { useEffect, useRef } from "react";

import {
  getWebSourceQualityLabel,
  humanizeFieldId,
} from "../formFieldState";
import type {
  AgentRequest,
  AgentStatus,
  ConversationMessage,
  PdfField,
} from "../formTypes";

type ConversationTranscriptProps = {
  agentStatus: AgentStatus;
  fields: PdfField[];
  messages: ConversationMessage[];
  showFullTranscript: boolean;
  visibleMessages: ConversationMessage[];
  onRetryGuidance: (request: AgentRequest) => void;
  onToggleFullTranscript: () => void;
};

export default function ConversationTranscript({
  agentStatus,
  fields,
  messages,
  showFullTranscript,
  visibleMessages,
  onRetryGuidance,
  onToggleFullTranscript,
}: ConversationTranscriptProps) {
  const conversationRef = useRef<HTMLDivElement>(null);
  const followLatestRef = useRef(true);

  useEffect(() => {
    const conversation = conversationRef.current;
    if (!conversation || !followLatestRef.current) {
      return;
    }
    conversation.scrollTop = conversation.scrollHeight;
  }, [visibleMessages.length, agentStatus]);

  return (
    <section className="agent-transcript">
      <div className="agent-transcript-heading">
        <div>
          <strong>Conversation</strong>
          <span>{messages.length} messages</span>
        </div>
        {messages.length > 2 ? (
          <button
            type="button"
            aria-controls="agent-conversation-log"
            aria-expanded={showFullTranscript}
            onClick={onToggleFullTranscript}
          >
            {showFullTranscript ? "Show recent only" : "Show full transcript"}
          </button>
        ) : null}
      </div>
      <div
        ref={conversationRef}
        className="agent-conversation"
        id="agent-conversation-log"
        aria-label="Form assistant conversation"
        role="log"
        tabIndex={0}
        onScroll={(event) => {
          const conversation = event.currentTarget;
          followLatestRef.current =
            conversation.scrollHeight -
              conversation.scrollTop -
              conversation.clientHeight <
            72;
        }}
      >
        {visibleMessages.map((message) => {
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
                  {message.role === "user" ? "You" : "Form assistant"}
                </strong>
                <div>
                  {messageField ? (
                    <span>
                      {messageField.label || humanizeFieldId(messageField.id)}
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
                    {message.webGuidance &&
                    message.webGuidance.sources.length > 0 ? (
                      <aside
                        className={`agent-web-guidance ${message.webGuidance.status}`}
                      >
                        <span>Live web guidance · Tavily</span>
                        <p>{message.webGuidance.notice}</p>
                        {message.webGuidance.sources.map((source) => (
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
                              {getWebSourceQualityLabel(source.source_quality)} ·{" "}
                              {source.hostname} · Retrieved {source.retrieved_at}
                              {source.form_version
                                ? ` · Form version ${source.form_version}`
                                : ""}
                            </small>
                          </article>
                        ))}
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
                            onRetryGuidance(
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
  );
}
