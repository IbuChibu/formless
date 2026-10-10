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
                              |
                              v
                      Nemotron Service
                              |
                              v
                    Nebius Token Factory

## Frontend

Responsible for:
- displaying PDF
- displaying questions
- recording voice
- displaying conversation
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
- `prompt_builder` prepares bounded untrusted context for Nemotron
- `response_parser` parses, canonicalizes, and validates model actions
- `value_normalizer` validates and safely normalizes field values

FastAPI and evaluation code import the public Form Agent package rather than
depending on those internal modules. The internal split does not create
multiple agents or allow any module to bypass the Nemotron Service.

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
does not store transcripts or add production analytics.

## Field update flow

For agent or voice input:
1. The frontend sends the explicit event, conversation state, and bounded form
   context to the Form Agent.
2. The Form Agent returns a typed action and resulting conversation state.
3. Backend code validates the proposal's field ID, type, and available options.
4. The frontend asks the user to confirm, edit, reject, or skip the proposal.
5. A separate confirmation event is validated before the value enters shared
   field state.
6. The frontend sends confirmed values to the existing PDF filling endpoint.

For manual or direct-on-form input, the explicit user edit is already a
confirmation. It updates the same shared state and uses the same PDF filling
endpoint. The AI never controls the manual drawer or edits its DOM.
