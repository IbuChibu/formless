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

---

## 2026-10-13 — Prior-answer recovery is explicit, bounded, and proposal-only

Decision:
The Form Agent may recover a user-supplied value from the existing bounded
request history only when the current message explicitly refers to an earlier
answer, the field type has a deterministic cue for that value, and exactly one
adapter-validated candidate remains. Recovery produces an ordinary unconfirmed
proposal. It cannot confirm a value, alter canonical field state, or use model
inference to choose between candidates.

Reason:
People naturally provide related answers together and reasonably expect the
assistant to remember them. Restricting recovery to explicit references and
field-specific deterministic extraction improves continuity without treating
the transcript as a hidden database or weakening the confirmation boundary.

Outcome:
On the unchanged Milestone 7.2 suite, all 47 turns completed, exact form-state
accuracy rose from 0.500 to 0.875, context retention reached 1.000, recovery
rose from 0.333 to 0.857, and invention and confirmation-boundary failures
remained zero.

---

## 2026-10-14 — Latest-turn semantics are deterministic before model fluency

Decision:
For bounded high-confidence cases, the active user message is interpreted
before Nemotron sees the turn. Whole-number words become reviewable digits;
`nobody` on a question that explicitly says to count yourself requires a
specific clarification; and dropdown near-matching is permitted only when one
option clears a strict unique similarity threshold. Bounded history remains
available for context and explicit prior-answer recovery, but it cannot replace
the newest answer. All results remain unconfirmed proposals.

Model explanations are also validated against active field metadata and
reviewed guidance. Unsupported explicit date formats and unsupported claims
that partial or estimated dates are acceptable receive the existing single
correction attempt, then a deterministic grounded fallback. Confirm-edit
acknowledgements explicitly identify the edited value used.

Reason:
The first real voice-like interview showed that successful speech recognition
does not guarantee conversational understanding. The model repeated an older
`nobody` answer after the user said `one`, while simple finite choices and
edited confirmations sounded mechanical. Deterministic handling is safer,
faster, and easier to evaluate for these closed cases than adding another
agent or stronger default model.

Outcome:
On the fixed Milestone 7.4 suite, latest-answer adherence improved from zero to
1.000, context retention from 0.500 to 1.000, contradictions from one to zero,
repetition from 0.125 to zero, and all 14 deterministic failures were fixed.
Canonical form-state accuracy and invention failures remained unchanged at
1.000 and zero. The prior 47-turn suite introduced no new failure identity.

---

## 2026-10-15 — Hands-free interruption uses a local activity gate

Decision:
While an explicitly started voice interview is speaking an already-visible
assistant response, the frontend may briefly open the microphone and analyse
only audio levels. After calibration, sustained speech-like activity cancels
speech synthesis, releases that detector, and starts the existing one-turn Web
Speech recognizer. A short spike is insufficient. The detector stops on every
speech/session exit, and `Answer now` plus typing remain permanent fallbacks.

Reason:
Requiring a button press whenever the user wants to answer early breaks the
intended human-helper rhythm. Full continuous recognition, audio streaming, or
a separate voice agent would add privacy, cost, and state risks. A bounded
local gate enables natural barge-in without interpreting words, sending audio
to Formless, or bypassing the existing transcript, proposal, and explicit
confirmation path.

---

## 2026-10-15 — Human-helper quality is a separate evaluation gate

Decision:
The conversation harness retains exact form state, grounding, and explicit
confirmation as a hard correctness gate, and adds a separate human-helper gate
for acknowledgement, context retention, side-question recovery, clarification,
workflow pressure, conversational burden, and speech suitability. Longer
synthetic interviews may use reproducible scripted branches. Optional model
judging can score human-helper qualities or compare matching reports blindly,
but cannot override deterministic correctness.

Reason:
The earlier surface-level naturalness heuristic could score concise,
non-repetitive replies highly even when a manual session still felt robotic.
Separating observable conversational behaviour from form correctness makes that
gap visible without weakening the safety boundary or making model taste the
source of truth. Fixed synthetic scenarios and suite digests preserve useful
before/after evidence; an autonomous generated user would not.

---

## 2026-10-16 — Volunteered facts remain bounded, unconfirmed conversation state

Decision:
When one message explicitly supplies answers for several real fields, the Form
Agent may retain at most five uniquely mapped, field-adapter-valid later
candidates in request-carried conversation state. Each candidate keeps the
user's original wording and prepared value. It can be offered only as a normal
reviewable proposal when the user explicitly refers back to it, and it is
removed after the relevant confirm, reject, skip, manual change, or replacement
transition. It is never canonical field data, model memory, persistence, or an
implicit confirmation.

Specific side questions and post-completion review requests are handled before
generic progression. Their answers come from bounded field metadata, reviewed
guidance, or canonical field state and return a `none` effect. Wording
explanations receive a deterministic field-subject anchor when needed so a
model's phrasing cannot lose conversational continuity.

Reason:
People often answer related questions together and expect a helper to remember
them, but treating a transcript as an unbounded fact store would create hidden
state and weaken the explicit-confirmation boundary. Bounded typed candidates
preserve useful context without applying facts. Deterministic side-question and
review routing prevents fluent model wording from overriding navigation,
confirmed values, or the user's latest request.

Outcome:
The unchanged `human-helper-experience-v1` suite completed 182 of 182 turns
with exact form-state accuracy and 1.000 volunteered-fact recall, side-question
recovery, acknowledgement, clarification success, interruption recovery, and
overall observed behaviour. Both evaluation gates passed with zero invention,
contradiction, deterministic, and confirmation-boundary failures.

---

## 2026-10-16 — Direct PDF editing uses normalized widget overlays

Decision:
The PDF Service returns each AcroForm widget rectangle as a one-based page and
normalized top-left coordinates tied to the existing stable field ID. The
frontend places accessible interaction targets over the PDF.js canvas and uses
field clicks only to open the shared canonical field editor. It does not write
or annotate PDF bytes in the browser.

Final review is also a view over canonical frontend state. A proposed value is
shown as proposed but remains outside the fill payload. Direct and manual values
enter that payload only when they satisfy the field's validation, and skipping
or clearing a changed answer removes it. The existing backend `/pdf/fill`
endpoint remains the only path that produces a changed preview or download.

Reason:
Normalized coordinates are independent of screen size and keep visual field
selection separate from PDF mutation. Reusing one field state prevents values
from diverging as the user moves between conversation, document interaction,
manual fallback, and final review, while preserving the explicit-confirmation
boundary for AI proposals.

---

## 2026-10-16 — Hands-free interruption favors avoiding self-interruption

Decision:
The local voice-activity gate calibrates against the assistant's audible
speaker leakage before it arms. Automatic microphone gain is disabled, browser
echo cancellation and noise suppression remain requested, and an interruption
requires sustained, varying speech-like activity materially above the observed
ambient and playback levels. A weak or ambiguous signal does not cancel the
assistant; the user can always select `Answer now` or type instead.

Reason:
The Web Speech synthesis API does not expose its output waveform, so a browser
cannot prove whether microphone speech came from the user or from its own
speakers. Treating every sustained sound as an interruption caused the helper
to cut off the ends of replies. A conservative gate makes false cancellation
less likely while keeping a clear manual fallback for speech that the browser
cannot distinguish safely.

---

## 2026-10-17 — Frontend presentation is split without splitting canonical state

Decision:
The frontend separates shared contracts, strict response parsing, pure
field-state helpers, reusable controls, and major presentation sections from
`App.tsx`. `App` remains the single current-form orchestration boundary and
continues to own canonical values, confirmation and skip state, proposals,
conversation state, and PDF-preview coordination. Extracted components receive
data and callbacks; they do not fetch, interpret agent prose, or create their
own form stores.

Reason:
The complete workflow had accumulated in one large component, making
accessibility, recovery, and responsive polish unnecessarily risky. Separating
stable responsibilities makes those changes easier to review and test without
introducing a state library, changing API contracts, or weakening the existing
single-state and explicit-confirmation decisions.

---

## 2026-10-17 — Form Agent policy is split behind a stable compatibility surface

Decision:
`conversation_policy` remains the established import surface but no longer
owns every conversation responsibility. Turn intent, model-action validation,
state transitions and closed effects, navigation and progression, and
deterministic action routing live in focused internal modules. The orchestrator
continues to coordinate one turn, and the public Form Agent package remains the
application boundary.

Reason:
The policy had grown to 2,103 lines and combined classification, transition,
validation, navigation, fallback, and effect concerns. Moving those concerns
behind the existing import surface reduces change risk without changing
prompts, provider calls, request or response contracts, explicit confirmation,
canonical state, PDF separation, or the one-agent architecture.

---

## 2026-10-17 — Reliability recovery is explicit and non-destructive

Decision:
Frontend connection, extraction, and completed-preview failures expose focused
retry actions. Extraction retry reuses the selected local file; fill retry
reuses canonical confirmed values; and a failed refresh leaves the last usable
PDF preview visible. Unsupported or unreadable form-field states explain the
AcroForm boundary without discarding the uploaded document. Keyboard users can
close the direct editor and final review with Escape and return to a stable
focus target, while status and drawer state remain available to assistive
technology.

Reason:
A demo-critical error should not make the user repeat an upload or lose already
reviewed answers. Keeping retries inside the existing `App` orchestration
boundary preserves one canonical workflow, avoids persistence or a second
state store, and makes failure recovery testable without weakening the rule
that only confirmed values reach PDF filling.
