# Architecture

Browser
    |
    v
React / TypeScript
    |
    | HTTP
    v
FastAPI
    |
    +---- PDF Service
    |
    +---- Form Agent
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

Must not:
- call Nebius directly
- manipulate PDF files
- contain agent reasoning

## FastAPI

Responsible for:
- API endpoints
- request validation
- coordinating services

## PDF Service

Responsible for:
- extracting PDF fields
- filling PDF fields
- producing completed PDFs

Must not:
- call an LLM

## Nemotron Service

Responsible only for:
- communicating with Nebius Token Factory

## Form Agent

Responsible for:
- conversation state
- deciding what context goes to Nemotron
- processing model actions
- deciding when clarification is needed
- managing confirmation