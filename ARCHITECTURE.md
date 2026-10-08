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
- deciding what context goes to Nemotron
- processing model actions
- deciding when clarification is needed
- marking proposed changes as requiring confirmation
- returning structured field proposals tied to real field IDs

Must not:
- edit PDF bytes
- bypass field validation
- convert an unconfirmed proposal into a confirmed value

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

## Field update flow

For agent or voice input:
1. The frontend sends the user's message and bounded form context to the Form Agent.
2. The Form Agent may return explanatory text or a structured field proposal.
3. Backend code validates the proposal's field ID, type, and available options.
4. The frontend asks the user to confirm, edit, reject, or skip the proposal.
5. A confirmed value enters the shared field state.
6. The frontend sends confirmed values to the existing PDF filling endpoint.

For manual or direct-on-form input, the explicit user edit is already a
confirmation. It updates the same shared state and uses the same PDF filling
endpoint. The AI never controls the manual drawer or edits its DOM.
