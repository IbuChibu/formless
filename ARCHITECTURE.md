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
     PDF Service          Form Agent
                         /          \
                        v            v
          Local official guidance  Nemotron Service
                 registry                 |
                                          v
                                Nebius Token Factory

## Frontend

Responsible for:
- displaying PDF
- displaying questions
- recording voice
- displaying conversation
- displaying attributable official-guidance sources returned by the backend
- showing progress
- keeping the current uploaded form's ephemeral field state
- keeping AI-proposed values separate from confirmed values
- presenting confirmation, correction, rejection, and skip controls
- sending only confirmed values to the PDF filling endpoint

Must not:
- call Nebius directly
- manipulate PDF files
- contain agent reasoning
- treat an AI proposal as a confirmed factual answer

## FastAPI

Responsible for:
- API endpoints
- request validation
- coordinating services

## PDF Service

Responsible for:
- extracting PDF fields
- returning stable field IDs and display metadata
- identifying explicitly supported form editions from exact local signatures
- returning widget geometry when direct-on-form editing is implemented
- filling PDF fields
- producing completed PDFs

Must not:
- call an LLM

## Nemotron Service

Responsible only for:
- communicating with Nebius Token Factory

## Form Agent

Responsible for:
- processing bounded conversation state received with each request
- validating explicit conversation events and state transitions
- deciding what context goes to Nemotron
- selecting bounded official guidance for an exact allowlisted form version
- processing model actions
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
- `conversation_policy` owns deterministic routing, allowed transitions, and
  response wording
- `answer_adapters` selects focused field-type interpreters from deterministic
  field metadata and returns a matched value, a specific clarification, or a
  signal that model interpretation is still needed
- `prompt_builder` prepares bounded untrusted context for Nemotron
- `official_guidance` loads the local allowlist, selects relevant excerpts, and
  prepares source attribution
- `response_parser` parses, canonicalizes, and validates model actions
- `value_normalizer` validates and safely normalizes field values

FastAPI and evaluation code import the public Form Agent package rather than
depending on those internal modules. The internal split does not create
multiple agents or allow any module to bypass the Nemotron Service.

## Official guidance

Known form identity is deterministic metadata produced during PDF extraction.
The neutral form catalog requires a matching title, field count, and small
field-ID signature before assigning a form ID and version. It does not download
instructions or call an AI service.

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

## Canonical field state

Every input surface operates on the same field records identified by the IDs
returned from PDF extraction. The current form session distinguishes:
- current confirmed value
- optional proposed value
- answer status: unanswered, proposed, confirmed, or skipped
- source of the latest change: agent, voice, direct PDF edit, or manual drawer

This state may remain in the frontend for the hackathon MVP. It does not require
a database. Conversation context can be sent explicitly to the Form Agent in a
bounded request rather than introducing persistence.

## Conversation state machine

The frontend sends the complete ephemeral conversation state and one explicit
event with each Form Agent request. The canonical phases are:
- `asking`
- `awaiting_answer`
- `awaiting_clarification`
- `awaiting_confirmation`
- `field_confirmed`
- `field_skipped`
- `form_complete`

An `awaiting_confirmation` state includes a pending proposal containing the
field ID and proposed value. Confirmation, edited confirmation, rejection, and
skip are explicit events; ordinary message events cannot confirm a proposal.
Every Form Agent response contains both a typed action and the resulting state,
so the frontend does not infer progression from assistant wording. The state is
validated on every request and is never stored by the backend.

After an explicit confirmation, edited confirmation, or skip, the backend
deterministically selects the next unanswered field. The response action still
identifies the field that was just resolved, while the resulting state points
to the next active field or `form_complete`. Its acknowledgement includes the
next field's real question without another model call. Explicit skip events
also carry the intended field ID so a stale repeated event cannot skip the new
active field. The `field_confirmed` and `field_skipped` phases remain available
for direct/manual field-state changes and compatibility with explicit advance
events, but the normal proposal-decision path progresses in one response.

## Agent evaluation

Agent evaluation is separate from runtime orchestration. The existing
single-turn evaluation checks focused actions, while the transcript evaluation
runs complete ephemeral state-machine conversations over bounded representative
fields extracted from the sample, household-support, USCIS I-9, and SBA
fixtures. Every scripted turn declares its expected action, conversation state,
confirmed values, and skipped fields.

Normal tests use deterministic Nemotron doubles and make no network requests.
The transcript evaluator may be run explicitly in live mode with the configured
Nebius credentials to report model latency and calls per evaluated field. It
does not store transcripts or add production analytics. Its offline adapter
comparison reruns the same transcripts with the previous narrow deterministic
interpreter to measure clarification re-prompts and invalid proposals without
weakening invention checks.

## Field update flow

For agent or voice input:
1. The frontend sends the explicit event, conversation state, and bounded form
   context to the Form Agent.
2. For explanatory turns, the Form Agent may select bounded local guidance for
   an exact allowlisted form version and active field.
3. The Form Agent first asks the selected field-type adapter to match or clarify
   common answers; genuinely complex interpretation can fall through to
   Nemotron.
4. The Form Agent returns a typed action, resulting conversation state, and any
   attributable guidance used by the explanation.
5. Backend code validates every deterministic or model proposal through the
   field adapter and the field's ID, type, and available options.
6. The frontend asks the user to confirm, edit, reject, or skip the proposal.
7. A separate confirmation event is validated before the value enters shared
   field state exactly once. Rejection keeps the same field active.
8. Confirmation, edited confirmation, and skip deterministically transition to
   the next unanswered field, or to form complete, without another model call.
9. The frontend sends confirmed values to the existing PDF filling endpoint.

For manual or direct-on-form input, the explicit user edit is already a
confirmation. It updates the same shared state and uses the same PDF filling
endpoint. The AI never controls the manual drawer or edits its DOM.
