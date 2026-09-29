# AGENTS.md

## Project
Voice-first AI assistant that helps users understand and complete
confusing PDF forms.

## Stack
Frontend: React + TypeScript + Vite
Backend: Python + FastAPI
AI: NVIDIA Nemotron via Nebius Token Factory
PDF: pypdf / PyMuPDF

## Rules

- Keep the architecture simple.
- Do not introduce new frameworks without approval.
- Do not implement future milestones early.
- Do not modify unrelated files.
- Prefer small changes.
- Add tests for backend functionality.
- Never let the AI invent factual information for the user.
- AI functionality and PDF manipulation must remain separate.

## Before coding
1. Read PROJECT_PLAN.md.
2. Read ARCHITECTURE.md.
3. Identify the current milestone.
4. Inspect relevant existing code.
5. State which files need changing.

## After coding
Report:
- files created
- files modified
- what changed
- how to test it
- whether the milestone acceptance criteria pass

Do not automatically begin the next milestone.