# Architecture Decisions

## 2026-09-29 — PDF first, online forms later

Decision:
The hackathon MVP supports uploaded fillable PDFs.

Reason:
PDF workflow is substantially easier to make reliable before the deadline.

Online/browser forms are explicitly out of scope for the initial submission.

---

## 2026-09-29 — No agent framework initially

Decision:
Agent orchestration will be implemented directly in Python.

Reason:
LangChain/LangGraph are unnecessary for the initial workflow and add complexity.

---

## 2026-09-29 — Voice added after text workflow

Decision:
The assistant must work fully through typed text before speech input/output is implemented.

Reason:
Voice should be an interface around the agent, not coupled to agent logic.

---

## 2026-10-08 — Conversation-first interface with a manual fallback

Decision:
The final product will make voice and text conversation the primary interface.
The existing manual field controls will remain available in a collapsible
"Edit all fields" drawer rather than being removed.

Reason:
The manual controls are useful for accessibility, corrections, review,
unsupported fields, demonstrations, and development. Keeping them as a fallback
does not require the user to experience the product as a traditional form
builder.

---

## 2026-10-08 — The agent proposes field changes but does not apply them

Decision:
The Form Agent will return structured proposals containing stable PDF field IDs
and candidate values. AI-proposed factual values must remain separate from
confirmed values until the user explicitly confirms or edits them.

Reason:
This preserves the user as the source of factual information, prevents model
output from silently changing a legal or financial form, and keeps AI logic
separate from PDF manipulation.

---

## 2026-10-08 — All input modes share one field state

Decision:
Voice, typed conversation, direct edits on the displayed PDF, and the manual
drawer will all update the same canonical field state through stable field IDs.
The AI will not interact with manual UI elements or maintain a duplicate copy of
the form.

Reason:
A single state model prevents conflicting answers, allows every input mode to
reuse the existing PDF filling endpoint, and makes correction and review
consistent across the product.

---

## 2026-10-10 — Official guidance is local, allowlisted, and version-specific

Decision:
Official guidance used by the Form Agent will come from small reviewed local
resources selected only for an exact recognized form ID and version. Guidance
responses expose the source and keep the official excerpt separate from the
assistant's plain-language explanation.

Reason:
This gives users attributable help without runtime crawling or general RAG,
prevents silently applying instructions from the wrong form edition, and keeps
external text inside the same untrusted-data boundary as PDF and user content.

---

## 2026-10-10 — Live web guidance is policy-gated and separate from reviewed guidance

Decision:
The Form Agent may use Tavily for one bounded search only when the user asks an
informational question and reviewed local guidance is insufficient. Search
eligibility and query construction are deterministic backend responsibilities.
Live results remain visibly separate from reviewed official guidance.

Reason:
This provides current, attributable help for unrecognized forms without giving
the model autonomous tool access or maintaining a large domain allowlist. The
query excludes PDF bytes, field values, proposals, personal answers, and
conversation history, while returned snippets and URLs are treated as
untrusted data and cannot cross the existing proposal-confirmation boundary.

---

## 2026-10-10 — Exact form editions may use reviewed PDF presentation profiles

Decision:
An exactly recognized PDF edition may use a small static profile to correct its
field labels, questions, visible order, narrowly scoped help text, and the
display labels mapped to verified AcroForm export states. The generic extractor
remains the fallback for every unrecognized PDF.

Reason:
Complex official AcroForms such as DS-11 can have stable widgets but ambiguous
nearby text geometry and machine-oriented export names. A reviewed,
version-specific mapping is deterministic, testable, and safer than asking an
LLM to reinterpret the form or broadening geometry heuristics for unrelated
PDFs.

---

## 2026-10-11 — Conversation text is separate from form effects

Decision:
The public Form Agent response contains a natural `assistant_message` and one
closed typed `effect`. Ordinary conversation uses a non-mutating effect;
proposals, confirmations, rejections, skips, field selection, and completion
remain explicit validated effects with canonical conversation state.

Reason:
The assistant should be able to converse naturally without making every useful
sentence double as a state-machine command. Keeping effects typed preserves the
existing safety boundary: model wording cannot mutate confirmed values or PDF
bytes.

---

## 2026-10-11 — Answer preparation preserves the original candidate

Decision:
Every prepared proposal retains the user's original candidate, the value
prepared for the form, and a concise transformation description when the two
differ. Deterministic field adapters run first. Names and identity data never
receive speculative spelling correction, and every visible transformation
requires explicit review.

Reason:
Formatting dates, numbers, options, capitalization, and light prose
presentation can reduce user effort, but silently rewriting factual information
would undermine trust and could change a legal or financial form answer.

---

## 2026-10-11 — Primary Nemotron selection is evaluation-gated

Decision:
Formless remains a single-agent, single-primary-model system. Before voice is
added, the current Lightning model will be compared with one stronger Nemotron
candidate through the same fixed live evaluation. A candidate may replace
Lightning as the single primary model only when it provides a material
conversation-quality improvement without a safety regression or unacceptable
latency increase.

Reason:
Model size alone does not establish that a form interview will be clearer,
safer, or responsive enough for voice. A controlled comparison makes the
tradeoff visible while avoiding the latency, cost, and failure modes of a
runtime cascade. Deterministic authority over state, tools, validation, and
confirmation remains unchanged regardless of the selected model.

Outcome:
The 11 October 2026 live comparison retained
`nvidia/Nemotron-3_5-Lightning`. The Ultra candidate preserved response validity
and state safety but reduced useful-next-step and conversation-repair rates and
was 4.419 times slower on the fixed scenarios. Formless therefore keeps one
Lightning model and adds no runtime fallback.

---

## 2026-10-11 — Navigation and corrections are closed state transitions

Decision:
Conversational references to fields are matched deterministically against the
bounded form schema. Selecting an unanswered field, reopening a skipped field,
and starting or cancelling a confirmed-value correction each return a distinct
typed effect. Replacement proposals retain the previous confirmed value and
use distinct replacement phases until an explicit confirmation event applies
the new value.

Reason:
Users need to move around and correct a form naturally, but assistant wording
must never become an implicit write operation. Keeping the old value canonical
through discussion, rejection, failures, and stale events prevents premature
PDF changes, while deterministic review responses avoid sending unrelated
personal values to the model.

---

## 2026-10-11 — The guided interview is a view over shared canonical state

Decision:
The primary typed experience emphasizes one active question, its extracted
section/page context, optional schema-derived quick answers, and a distinct
proposal review. Quick answers and typed answers dispatch the same Form Agent
message event. The full transcript stays available, while the manual field
drawer remains a collapsed fallback over the same frontend field state.

Reason:
A focused interview is calmer than exposing a general chat plus workflow
controls, but it must not create a second state path. Reusing the existing
event, proposal, explicit-confirmation, and PDF-preview flow prevents quick
controls or presentation changes from bypassing validation or writing an
unconfirmed answer.

---

## 2026-10-12 — Voice is an adapter over the typed interview

Decision:
Voice capture and speech output remain frontend browser capabilities. Recognized
speech is an editable draft and enters the application only through the same
Form Agent message event used by typed text. Spoken output reads the same
visible `assistant_message`. Cancelling capture, stopping speech, permission
failure, and unsupported browser capabilities have no form effect.

Reason:
A separate voice agent or voice-owned field state would duplicate routing,
validation, and confirmation logic and could weaken the PDF safety boundary.
Keeping voice as an input/output adapter preserves one canonical conversation,
one explicit proposal review, one confirmed field state, and a permanent typed
fallback while still delivering the voice-first interaction needed for the
hackathon demonstration.

---

## 2026-10-12 — Voice uses an explicit turn-based interview session

Decision:
Starting voice creates a frontend-only, turn-based session over the existing
Form Agent. The assistant speaks its already-visible response, opens one
listening turn, sends the completed transcript through the existing message
path, and continues from the returned typed effect and conversation state.
Exact spoken confirmation phrases map to the existing explicit confirmation
event only while the matching proposal card is visibly pending.

Reason:
Dictation controls do not reproduce the intended experience of a patient human
helper who asks, listens, checks, and moves to the next question. A bounded
session provides that rhythm without always-on recording, a voice-specific
agent, duplicate form state, or direct speech-to-PDF writes. Restricting spoken
confirmation to visible pending proposals retains the same review boundary as
the typed interface.

---

## 2026-10-13 — Conversation changes are gated by an artifact-producing baseline

Decision:
Before changing the production Form Agent again, Formless runs fixed synthetic
persona conversations through its existing public application boundary. The
evaluation harness owns only test scenarios, an ephemeral mirror of typed
effects, deterministic scoring, an optional qualitative Nemotron rubric, and
JSON/Markdown reporting. Exact form state and closed-effect expectations remain
authoritative. Candidate changes are compared only against reports with the
same scenario-suite digest.

Reason:
Short happy-path tests can pass while real conversational phrasing still loses
values, repeats questions, or blocks recovery. Free-form model judging alone is
also unstable and can reward fluent prose despite an incorrect form. Saving the
complete transcript, expected and actual state, stable deterministic failures,
and bounded qualitative reasons makes the weaknesses reproducible without
adding production analytics or storing real personal information.

Outcome:
The first live eight-scenario baseline showed that warm wording and safe
confirmation boundaries are not the primary bottleneck. The largest gaps are
active-value extraction from bundled or conversational answers, spoken-date
normalization, retaining volunteered later-field context, and natural
return-to-field navigation. Those findings define Milestone 7.3; no production
Form Agent behavior changed while the baseline was recorded.
