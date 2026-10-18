# Architecture

Voice / Text / PDF field click / Manual drawer
                    |
                    v
            React / TypeScript
            Shared form state
        (proposed and confirmed values)
                    |
                    | HTTP
                    v
                 FastAPI
                    |
          +---------+---------+
          |                   |
          v                   v
     PDF Service                Form Agent
                         /          |          \
                        v           v           v
          Local official     Tavily Service   Nemotron Service
          guidance registry        |                 |
                                   v                 v
                              Tavily Search  Nebius Token Factory

## Frontend

Responsible for:
- displaying PDF
- rendering normalized AcroForm widget coordinates as a browser overlay tied to
  stable field IDs, navigating to the active field, and opening a focused field
  editor when a supported widget is selected
- displaying questions
- opening the guided interview with one optional conversational support setup,
  keeping the user's explicit assistance preferences only for the current PDF
  session, and allowing those preferences to be changed or skipped
- keeping checkbox and radio preference controls collapsed behind `Adjust how
  I help` as a direct fallback rather than making them the primary introduction
- visually adapting the preferred input emphasis without treating a voice
  preference as microphone consent or starting a voice session
- starting a turn-based browser voice interview only after an explicit user
  action
- speaking the same already-visible assistant message, then opening one bounded
  listening turn rather than recording continuously
- monitoring only transient local microphone levels while that spoken response
  is active, so sustained user speech can stop it and open the same bounded
  listening turn
- keeping the latest recognized speech visible and correctable while sending a
  completed utterance through the same Form Agent message path as typed text
- mapping only a small exact set of spoken decisions to existing explicit
  confirm, reject, and skip events, with confirmation enabled only while the
  matching proposal is visibly pending
- pausing, resuming, ending, or interrupting a voice session without changing
  canonical field state
- presenting permission, listening, processing, retry, unsupported-browser, and
  speech-output failure states without removing the typed composer
- displaying conversation
- presenting the conversation as a focused one-question-at-a-time interview
  using section, page, question, and progress metadata from extracted fields
- exposing validated finite choices as optional quick answers that dispatch the
  same Form Agent message event as the typed composer
- retaining the full current-form transcript while visually prioritizing the
  active question and latest conversational turn
- rendering the assistant's natural-language message separately from any typed
  form effect
- showing original and prepared proposal values together when formatting
  changes visible text
- displaying attributable official-guidance sources returned by the backend
- distinguishing attributable live web guidance from reviewed official guidance
- showing progress
- keeping the current uploaded form's ephemeral field state
- keeping AI-proposed values separate from confirmed values
- presenting confirmation, correction, rejection, and skip controls
- keeping the manual field drawer, quick answers, conversation, and proposal
  review on the same ephemeral canonical field state
- presenting a final review of completed, proposed, skipped, and unanswered
  supported fields from that same state
- sending only confirmed values to the PDF filling endpoint
- exposing connection, extraction, and completed-preview retry controls that
  reuse the retained upload and canonical state rather than creating a second
  workflow or discarding the document
- providing named live status regions, keyboard-operable PDF navigation and
  field targets, explicit drawer state, Escape handling, and focus recovery for
  the direct editor and final review

Frontend internals preserve one orchestration boundary while separating stable
responsibilities:
- `App` owns the current ephemeral session, canonical field values, confirmed
  and skipped IDs, conversation state, PDF-preview coordination, and the
  callbacks that connect input modes; it also owns the current explicit
  assistance preferences and clears them on PDF replacement
- `formTypes` owns the shared TypeScript contracts used by those boundaries
- `api` owns the base URL and provider-independent HTTP/error validation helpers
- `agentResponse` strictly parses and validates the Form Agent response,
  effect, guidance, remembered-candidate, and state-transition contract before
  `App` can apply it
- `formFieldState` owns pure field compatibility, initial-value, request-field,
  review-status, grouping, display, and bounded guidance-intent helpers
- `FieldControls` owns the reusable manual, direct-edit, and proposal inputs
- components under `components` render the header, upload surface, document
  workspace, active question, transcript, proposal review, final review, and
  manual drawer from explicit props and callbacks

Extracted presentation components do not fetch, own a second field store,
interpret free-form agent text, or apply PDF changes. Moving between components
therefore does not change the canonical-state or explicit-confirmation rules.
Recovery follows the same rule: `App` repeats the failed health, extraction, or
fill request from retained local state. A failed extraction or fill never
replaces or overwrites the user's uploaded PDF, and the last usable preview
remains available whenever one exists.

Must not:
- call Nebius directly
- manipulate PDF files
- contain agent reasoning
- treat an AI proposal as a confirmed factual answer
- let browser speech recognition or speech synthesis mutate canonical field
  state, create a second conversation path, or confirm anything when no matching
  proposal is visibly pending

## Voice interview

The browser voice layer has two focused responsibilities. `useVoiceAssistant`
owns the Web Speech API lifecycle, including one-shot recognition, editable
transcript state, speech synthesis, cancellation, unsupported capability, and
stale-callback guards. Its small `voiceInterruptionDetector` dependency uses
Web Audio only while assistant speech is active: it calibrates to local noise,
requires sustained activity, and releases the microphone before recognition
starts. `useVoiceInterview` owns the frontend-only turn loop:

```text
explicit start
    -> visible assistant response is spoken and local interruption arms
    -> user speech may stop the response
    -> one listening turn
    -> visible completed transcript
    -> existing Form Agent message or closed event
    -> validated response and effect
    -> next spoken response
```

The voice interview does not parse form values or update fields. Ordinary
speech is sent as the existing `message` event. A field-scoped skip uses the
existing `skip` event. A bounded affirmative phrase becomes the existing
`confirm` event only while canonical conversation state contains a visible
pending proposal. A spoken correction first rejects that proposal, then sends
the user-stated replacement through the ordinary answer path; the replacement
creates a new proposal and still requires confirmation.

The activity detector is not a recognizer: it observes no words, buffers no
audio, and dispatches no form action. At the start of each spoken response it
briefly calibrates against ambient sound and speaker-to-microphone leakage. The
browser is asked to apply echo cancellation and noise suppression without
automatic gain control. The gate arms only after calibration and requires
sustained, varying speech-like activity above both the ambient threshold and
the calibrated playback ceiling. Conservative misses remain recoverable through
the permanent `Answer now` and typed controls.

The detector stops on speech completion, manual interruption, recognition
start, pause, end, error, form change, or unmount.
The interview loop stops on pause, end, microphone failure, provider failure,
or form change. Audio is never uploaded or stored. Typed conversation,
`Answer now`, proposal buttons, and the manual drawer remain available
throughout and operate on the same state.

## FastAPI

Responsible for:
- API endpoints
- request validation
- coordinating services

## PDF Service

Responsible for:
- extracting PDF fields
- returning stable field IDs and display metadata
- validating button-widget appearance/export states and returning deterministic
  supported, editable, and capability-reason metadata
- identifying explicitly supported form editions from exact local signatures
- applying reviewed display metadata and visible-option mappings only for an
  exact recognized form edition
- returning every available widget rectangle as normalized top-left page
  coordinates tied to its stable field ID, including repeated widgets
- filling PDF fields
- validating submitted choice values against the same capability rules used
  during extraction
- producing completed PDFs

Must not:
- call an LLM

The frontend overlay is interaction metadata, not a second PDF editor. It is
positioned over the PDF.js-rendered page using the normalized coordinates from
extraction. A click updates the same React field state used by conversation and
the manual drawer. Only confirmed changed values are sent back to `/pdf/fill`,
and the PDF Service produces the refreshed preview and downloadable file.

## Nemotron Service

Responsible only for:
- communicating with Nebius Token Factory

## Tavily Service

Responsible only for:
- reading server-side Tavily configuration
- communicating with the Tavily Search API
- mapping timeouts, provider failures, and malformed responses to controlled errors

It does not decide when to search, build form-specific queries, rank sources,
or process conversation state.

## Form Agent

Responsible for:
- processing bounded conversation state received with each request
- validating bounded assistance preferences received with each request and
  using them only to shape wording, pace, explanation depth, and spoken
  readability
- deterministically mapping only clear support requests made during the
  introduction or interview into the closed assistance-preference schema
- validating explicit conversation events and state transitions
- deciding what context goes to Nemotron
- selecting bounded official guidance for an exact allowlisted form version
- deterministically deciding whether an informational turn needs live guidance
- building non-personal search queries from bounded form and field metadata
- validating, ranking, labeling, and bounding live sources before model use
- processing model actions
- preparing user-supplied candidate values through deterministic field-aware
  formatting before they become reviewable proposals
- retaining at most five uniquely mapped, adapter-valid later-field candidates
  in request-carried conversation state when a user explicitly volunteers
  several answers together
- recovering a previously volunteered candidate only when the user explicitly
  points back to it and one field-specific value can be validated from bounded
  conversation state or request history
- returning a natural assistant message separately from a closed validated
  effect describing any workflow or form-state consequence
- deciding when clarification is needed
- marking proposed changes as requiring confirmation
- returning structured field proposals tied to real field IDs

Must not:
- edit PDF bytes
- bypass field validation
- convert an unconfirmed proposal into a confirmed value

The Form Agent is one service boundary with small internal modules:
- `models` owns validated request, field, message, and action contracts
- `orchestrator` coordinates one turn and is the package's public service
- `conversation_policy` is the stable policy import surface and re-exports the
  established non-private policy functions from their focused owners
- `intent_policy` classifies bounded turn intent and tracks explanation-repair
  depth without producing a form effect
- `action_validation` checks model-authored actions and explanations against
  the active turn, field context, and approved guidance before they can proceed
- `state_machine` validates allowed events, owns conversation-phase changes,
  and converts validated actions into closed typed effects
- `navigation_policy` builds deterministic field-selection, correction,
  progress, completion, clarification, and next-question actions
- `conversation_actions` routes deterministic events and adapter results,
  provides controlled fallbacks, and normalizes action messages
- `answer_adapters` selects focused field-type interpreters from deterministic
  field metadata and returns a matched value, a specific clarification, or a
  signal that model interpretation is still needed; it also owns bounded,
  field-specific extraction and recovery of explicitly volunteered prior
  answers. Numeric adapters recognize bounded whole-number words, and finite-
  choice adapters accept a near-match only when one option clears a strict
  unique similarity threshold. A count-yourself question treats `nobody` as
  ambiguous rather than silently storing zero
- `answer_preparation` preserves the original candidate, applies conservative
  field-aware presentation changes, records the transformation, and verifies
  that factual meaning was not changed
- `prompt_builder` prepares bounded untrusted context for Nemotron
- `official_guidance` loads the local allowlist, selects relevant excerpts, and
  prepares source attribution
- `response_parser` parses, canonicalizes, and validates model actions
- `value_normalizer` validates and safely normalizes field values

FastAPI and evaluation code import the public Form Agent package rather than
depending on those internal modules. Existing policy callers use the
`conversation_policy` compatibility surface, so module ownership can change
without changing the service contract. The internal split does not create
multiple agents or allow any module to bypass the Nemotron Service.

The latest user message is authoritative for the current turn; bounded history
is context, not a replacement answer. Model explanations are checked against
the active field and reviewed guidance before they are returned. An explicit
date format or claim that a partial or estimated date is acceptable is rejected
unless the relevant constraint appears in that trusted context. The existing
single correction attempt may repair the explanation; otherwise deterministic
grounded wording is returned with no form effect.

## Official guidance

Known form identity is deterministic metadata produced during PDF extraction.
The neutral form catalog requires a matching title, field count, and small
field-ID signature before assigning a form ID and version. It does not download
instructions or call an AI service.

An exact recognized edition may also have a reviewed PDF presentation profile.
The profile can correct field labels, questions, section order, narrowly scoped
help text, and the display labels for verified choice export states. It never
changes stable PDF field IDs, invents form instructions, or weakens capability
validation. During filling, a displayed choice is translated back to its real
AcroForm export state only after the same exact-edition identity check. Unknown
forms continue to use the generic geometry-based metadata path. The DS-11
04-2025 profile uses this boundary to avoid attaching adjacent passport-book
help text to the applicant-name field and to keep its multi-widget controls as
single logical fields.

Official guidance is stored as small local JSON resources keyed by that exact
form ID and version. Every resource records its title, issuing organisation,
HTTPS source URL, form version, retrieval date, and scoped paraphrased
excerpts. Source hosts are allowlisted in backend code. Selection uses exact
field IDs, field-ID prefixes, sections, and a small fixed topic vocabulary; it
does not use embeddings, a vector database, or runtime web retrieval.

At most two excerpts and 1,000 excerpt characters can enter one Form Agent
turn. The prompt places them inside the same untrusted context boundary as PDF
text and user content. Guidance may support an explanation, but it can never
supply or confirm the user's personal field value. The response returns the
selected excerpts and source metadata separately from the assistant's
plain-language explanation, allowing the frontend to label and link the
official source. If no exact source is available for an official-purpose or
rule question, the agent says so instead of substituting another form version
or inferring an answer.

## Tavily integration (Milestone 6.13.1)

Tavily is a retrieval tool inside the existing Form Agent, not a second
agent and not a frontend integration. The existing Form Agent endpoint remains
the only conversational API:

```text
Form Agent request
       |
       v
Validate state and event
       |
       v
Select reviewed local guidance
       |
       +-- sufficient --------------------------+
       |                                        |
       v                                        |
Deterministic web-guidance policy               |
       |                                        |
       +-- not eligible --> grounded fallback   |
       |                                        |
       v                                        |
Tavily Service                                  |
       |                                        |
       v                                        |
Validate, rank, label, and bound results        |
       |                                        |
       +----------------------------------------+
       |
       v
Prompt builder -> Nemotron Service -> typed explanation response
```

The responsibilities remain separated:
- `orchestrator` controls the turn and may request at most one Tavily lookup;
  subsequent Nemotron processing retains the existing structured-output
  correction limit
- `web_guidance` owns deterministic eligibility policy, safe query construction,
  result validation, source-quality labeling, deduplication, ranking, and bounds
- `tavily_service` owns only Tavily configuration, HTTP transport, timeout and
  provider-error handling, and response parsing
- `prompt_builder` accepts only normalized bounded results and treats their text
  as untrusted context
- `models` keeps live web citations separate from reviewed official-guidance
  citations while preserving the existing typed action contract

The frontend continues to send ordinary Form Agent events. It does not receive
the Tavily key, construct provider payloads, or call Tavily directly. Live web
sources appear as metadata on an explanation and cannot alter conversation
phase, create a proposal, confirm a value, or invoke the PDF Service.

Reviewed local guidance remains the first choice. When it is insufficient, the
deterministic policy may allow a bounded search only for an informational user
request. Answer, confirmation, rejection, skip, navigation, and background
turns never search. Search queries exclude uploaded PDF bytes, field values,
proposals, personal answers, and conversation history.

General web results are labeled as live web guidance, not reviewed official
guidance. Provider text and URLs are validated outside the model, and only
public HTTPS sources within fixed result and character limits can reach
Nemotron. Failure, weak evidence, or conflicting sources produces a grounded
uncertainty or unavailable response rather than another search, a personal
answer, or an authoritative rule.

Before ranking or prompt construction, every Tavily result passes a
deterministic relevance gate. The gate compares only bounded form identity,
known issuer, explicit version, active-field question, and controlled topic
metadata with the result title, public URL, and bounded snippet. Generic terms
such as `name`, `address`, `application`, and `form` cannot establish
relevance. Recognized forms require form or issuer evidence plus field context;
unrecognized forms require an exact distinctive form-title match or form code
plus active-field evidence. Results that explicitly identify a different form
version are rejected. Discarded results never enter Nemotron context or
response citations.

If no relevant result remains, the orchestrator returns a deterministic
`explain` action with web-guidance status `empty` before prompt construction;
Nemotron is not called. If Tavily is unconfigured or cannot complete the
lookup, the same safe response boundary uses the distinct `unavailable` status
and a provider-specific recovery notice. Both outcomes state that the form
schema and verified guidance cannot establish the requested meaning, purpose,
rule, or information source, preserve the current active field and conversation
phase, and offer retry, skip, or manual continuation. They contain no source
citations and cannot infer a purpose or change form state.

## Canonical field state

Every input surface operates on the same field records identified by the IDs
returned from PDF extraction. The current form session distinguishes:
- current confirmed value
- optional proposed value
- optional proposal presentation details: original value, prepared value, and
  a concise transformation description
- answer status: unanswered, proposed, confirmed, or skipped
- source of the latest change: agent, voice, direct PDF edit, or manual drawer

This state may remain in the frontend for the hackathon MVP. It does not require
a database. Conversation context can be sent explicitly to the Form Agent in a
bounded request rather than introducing persistence.

## Session-only assistance preferences

After a PDF is extracted, the Form Agent enters a `support_setup` phase before
the first field. It asks what tends to make forms difficult, accepts a natural
answer, and asks whether speaking, typing, or either is preferred when that is
still unclear. The user may say `just start` at either step. Only clear requests
are mapped deterministically to the closed preference schema; an identity,
diagnosis, or ambiguous difficulty statement receives a neutral follow-up
instead of an inferred preference.

The available support needs are explicit communication choices: plain
language, slower pacing, help organising supplied details, clearer review
reassurance, explanation of unfamiliar bureaucracy wording, and one optional
bounded note. A separate interaction preference may be standard, voice, or
typing. English is the only valid assistance language until a later reviewed
language milestone. The checkbox and radio controls expose the same object only
after the user opens `Adjust how I help`.

`App` owns this object for the current PDF session and includes it in each Form
Agent request. Replacing the PDF clears it. The backend accepts only the closed
preference values, requires unique needs, limits the optional note to 200
characters, and treats that note as untrusted context. The prompt builder
derives trusted style instructions from the closed values; it never turns the
free-text note into a system instruction.

Preference updates returned from conversation use a closed
`assistance_preferences_updated` effect. `App` validates and applies that effect
without treating it as a form mutation. Preferences are not canonical form
data, model-inferred profiles, diagnoses, analytics, or persistence. They may
alter presentation but cannot alter factual meaning, available options,
validation, guidance eligibility, explicit confirmation, or PDF filling.
Selecting voice changes emphasis only; microphone access still begins solely
through the existing explicit voice-session start.

## Conversation state machine

The frontend sends the complete ephemeral conversation state and one explicit
event with each Form Agent request. The canonical phases are:
- `support_setup`, with an explicit `needs`, `needs_after_interaction`, or
  `interaction` step and no active form field
- `asking`
- `awaiting_answer`
- `awaiting_clarification`
- `awaiting_confirmation`
- `awaiting_replacement`
- `awaiting_replacement_confirmation`
- `field_confirmed`
- `field_skipped`
- `form_complete`

An `awaiting_confirmation` state includes a pending proposal containing the
field ID and proposed value. An `awaiting_replacement_confirmation` state also
retains the previous confirmed value and marks the pending operation as a
replacement, allowing stale corrections to be rejected before any effect is
returned. The existing confirmed value remains canonical while the assistant
is in either replacement phase. Conversation state may also contain at most
five uniquely keyed remembered candidates for real unanswered fields. Each
candidate retains the user's original wording and one adapter-valid prepared
value, but it is neither confirmed nor canonical form data. Confirmation,
edited confirmation, rejection, skip, and correction cancellation are explicit
events; ordinary message events cannot confirm a proposal.
Every Form Agent response contains a primary `assistant_message`, one closed
typed `effect`, and the resulting state, so the frontend does not infer
progression from assistant wording. A `none` effect represents successful
non-mutating conversation. Other effects represent a pending proposal,
replacement proposal, confirmation, rejection, skip, field selection, skipped-
field reopening, correction start or cancellation, or completion. The state is
validated on every request and is never stored by the backend.

Conversational field references are resolved deterministically against bounded
question, label, and section text. Exact and normalized matches run before any
model call. A single status-compatible match can produce a closed navigation,
reopen, or correction effect; multiple matches produce a bounded clarification
and no transition. Read-only review summaries and specifically requested
confirmed values come directly from canonical field state and use a `none`
effect.

When a user explicitly says that an answer was supplied earlier, deterministic
recovery checks request-carried remembered candidates before the bounded
history already present in the request. It accepts a value only when a field-
specific cue yields one adapter-validated candidate; zero candidates fall back
to normal interpretation and multiple candidates require clarification.
Recovered values still become proposals and cross the same explicit
confirmation boundary as current-message answers. A remembered candidate is
removed when its field is confirmed, rejected, skipped, manually changed, or
otherwise leaves the relevant unanswered state.

Active-field informational and wording questions are resolved before global
navigation or value interpretation. They preserve the active field, use a
`none` effect, and include a deterministic field-subject anchor when model
wording would otherwise make the return to the current question ambiguous.
Form-complete summaries, read-backs, and specific value questions are generated
from canonical field state. Correction and cancellation continue through the
existing typed replacement transitions; rejecting a replacement preserves the
old confirmed value and exits that correction attempt.

After an explicit confirmation, edited confirmation, or skip, the backend
deterministically selects the next unanswered field. The response action still
identifies the field that was just resolved internally, while the public effect
identifies it for the frontend and the resulting state points
to the next active field or `form_complete`. Its acknowledgement includes the
next field's real question without another model call. Explicit skip events
also carry the intended field ID so a stale repeated event cannot skip the new
active field. The `field_confirmed` and `field_skipped` phases remain available
for direct/manual field-state changes and compatibility with explicit advance
events, but the normal proposal-decision path progresses in one response.

## Agent evaluation

Agent evaluation is separate from runtime orchestration and has four layers.
The single-turn evaluation checks focused actions. The curated transcript
evaluation runs known complete state-machine paths over bounded representative
fields extracted from the sample, household-support, USCIS I-9, SBA, and DS-11
fixtures. The conversation harness runs deliberately messy, persona-led
interviews through the public Form Agent application boundary and retains a
complete version-comparable artifact. Its human-helper suite runs longer
interviews and measures whether the same safe workflow is attentive, adaptive,
low-effort, and suitable for spoken delivery.

The conversation harness remains under `backend/evaluations` and imports the
public Form Agent package; production code never imports evaluation code. Its
versioned JSON scenarios use synthetic information and select real fields by ID
from the existing PDF fixtures. The simulator can call
`FormAgentService.respond` in process or post the identical request to a running
`/agent/respond` endpoint. It mirrors the frontend's closed effect handling in
ephemeral memory: proposal effects do not change fields, confirmed effects
write one validated value, skipped effects mark one field, and reopened effects
restore one field to unanswered. It never fills a PDF.

For every turn the harness records the event and visible user wording, request
state, field state before and after, assistant message, typed effect, resulting
state, latency, expectation failures, and errors. Exact state/effect checks,
user-grounded proposals, required and forbidden message phrases, response
length, context-tagged turns, latest-answer use, contradictions, repetition,
clarification, and recovery are deterministic. An optional Nemotron judge adds
a bounded qualitative rubric for naturalness, context awareness,
clarification, recovery, and invention, but cannot turn an incorrect form state
into a pass. Latest-answer metrics are reported only for suites with explicitly
tagged turns.

Human-helper scenarios add observable behavioural expectations without
requiring one exact sentence. They can check whether a response addresses the
latest request, acknowledges supplied information, returns to the active form
question, identifies a missing detail, avoids re-asking known information,
avoids unnecessary advancement, limits question burden, and remains concise
enough for speech. Each configured check records a named pass or failure.
Versioned deterministic branches may select the next scripted user utterance
from the previous visible response, typed effect, or check outcome; the chosen
branch is retained in the report.

Suite reports expose two separate gates. The correctness gate covers completed
turns, exact canonical form state, grounding, explicit confirmation, and
transcript/state contradictions. The human-helper gate covers volunteered-fact
recall, redundant questions, side-question and interruption recovery,
unnecessary workflow pressure, acknowledgement, clarification, conversational
burden, and speech suitability. Human-helper fluency never compensates for a
correctness failure. An optional pairwise command compares matching baseline
and candidate transcripts as label-blinded A/B examples, while deterministic
suite identity and state evidence remain authoritative.

Each JSON and Markdown report includes the fixed scenario-suite digest, target,
model, optional judge model, Git revision, label, timestamp, expected result,
actual state, full transcript, metrics, and failure reasons. Comparison is
allowed only for the same suite digest. Metric deltas and deterministic failure
identities show whether a production change fixed or introduced behavior;
free-form judge wording remains visible in each report but is not used as a
stable failure identity.

Normal tests use deterministic Nemotron doubles and make no network requests.
The transcript evaluator may be run explicitly in live mode with the configured
Nebius credentials to report model latency and calls per evaluated field. It
does not add production analytics. The conversation harness writes explicit
local artifacts under `backend/evaluations/results`, which are ignored by Git
and contain synthetic evaluation data only. The transcript evaluator's offline
adapter comparison reruns the same transcripts with the previous narrow
deterministic interpreter to measure clarification re-prompts and invalid
proposals without weakening invention checks. The transcript report also
records prepared-value acceptance, user edits, transformed proposals, and
unsafe transformations.

## Field update flow

For agent or voice input:
1. The frontend sends the explicit event, conversation state, and bounded form
   context to the Form Agent.
2. For explanatory turns, the Form Agent first selects bounded local guidance
   for an exact allowlisted form version and active field. If that is
   insufficient, deterministic policy may perform one bounded Tavily lookup.
3. The Form Agent first asks the selected field-type adapter to match or clarify
   common answers; genuinely complex interpretation can fall through to
   Nemotron.
4. The answer-preparation layer preserves the user's original candidate,
   applies only conservative field-aware formatting, and records any visible
   transformation.
5. Backend code validates every deterministic or model proposal through the
   field adapter and the field's ID, type, and available options.
6. The Form Agent returns a natural assistant message, one typed effect,
   resulting conversation state, and any attributable reviewed or live
   guidance used by the explanation.
7. The frontend shows original and prepared values together when they differ,
   then asks the user to confirm, edit, use the original when valid, reject, or
   skip the proposal.
8. A separate confirmation event is validated before the value enters shared
   field state exactly once. Rejection keeps the same field active. For a
   replacement proposal, rejection or cancellation preserves the previous
   confirmed value and the frontend does not update the PDF preview.
9. Confirmation, edited confirmation, and skip deterministically transition to
   the next unanswered field, or to form complete, without another model call.
10. The frontend sends confirmed values to the existing PDF filling endpoint.

For manual or direct-on-form input, the explicit user edit is already a
confirmation. It updates the same shared state and uses the same PDF filling
endpoint. The AI never controls the manual drawer or edits its DOM.
