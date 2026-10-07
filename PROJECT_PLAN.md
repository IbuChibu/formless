# Project Plan

## Product

A voice-first assistant that helps people complete confusing forms.

The user has the factual knowledge.

The AI helps them:
- understand questions
- answer conversationally
- identify missing information
- express answers appropriately
- review answers
- fill the final form

## Hackathon

Nebius x NVIDIA Global AI Hackathon

Track:
Best Apps and Agents

Deadline:
30 October 2026

Required technology:
- NVIDIA Nemotron
- Nebius Token Factory

---

# Milestone 1 — Foundation

Status: COMPLETE

Goal:
React frontend and FastAPI backend can communicate.

Acceptance criteria:
- frontend runs
- backend runs
- GET /health works
- frontend successfully calls /health

Do not implement:
- PDFs
- AI
- voice
- database

---

# Milestone 2 — PDF extraction

Status: COMPLETE

Goal:
Upload fillable PDF and extract fields.

Acceptance criteria:
- PDF can be uploaded
- AcroForm fields detected
- field IDs returned
- field types returned
- options returned where applicable
- tests pass

---

# Milestone 3 — PDF filling

Status: COMPLETE

Goal:
Programmatically populate a PDF.

Acceptance criteria:
- API accepts field/value mapping
- new PDF generated
- original PDF preserved
- text fields work
- supported choice fields work

---

# Milestone 4 — Basic UI

Status: COMPLETE

Goal:
Provide a basic manual form-filling UI using the existing PDF APIs.

User flow:
- select a local fillable PDF
- display the selected PDF in the browser
- upload the PDF to POST /pdf/extract
- display the extracted fields
- render text, dropdown, and checkbox inputs
- submit the current field/value mapping to POST /pdf/fill
- display the returned filled PDF as the latest preview
- download the latest completed PDF

Live preview behavior:
- the original PDF is displayed immediately using the browser's native PDF rendering
- field changes are sent to POST /pdf/fill after a short debounce
- the latest successful filled PDF automatically replaces the previous preview
- the frontend displays returned PDF bytes but does not manipulate PDF contents

Acceptance criteria:
- a local PDF can be selected
- the selected PDF is visible in the UI
- extracted fields are displayed
- text fields can be edited
- dropdown options can be selected
- checkboxes can be toggled
- field changes update the visible PDF preview without a separate preview action
- the latest completed PDF can be downloaded
- extraction, filling, loading, and error states are visible
- frontend production build passes
- existing backend tests pass

Do not implement:
- client-side PDF manipulation
- custom or advanced PDF viewer
- AI or Nemotron integration
- voice input or output
- authentication
- persistence or database
- online/browser form support

---

# Milestone 4.5 — USCIS I-9 compatibility

Status: COMPLETE

Goal:
Reliably extract, edit, preview, and download the bundled USCIS I-9 AcroForm
through the existing PDF workflow.

Acceptance criteria:
- extraction returns the I-9's 128 terminal form fields
- non-fillable structural field groups are not returned as user inputs
- text, multiline text, dropdown, and checkbox fields have appropriate UI controls
- all supported I-9 fields can be submitted in one fill request
- nested and repeated-widget fields store the submitted values
- updated widgets contain usable appearance streams
- the generated PDF remains interactive
- the original I-9 fixture remains unchanged
- a rendered populated application page is visually legible
- existing backend tests pass
- frontend production build passes

Do not implement:
- I-9-specific business rules or legal guidance
- execution of PDF JavaScript, calculations, or validation actions
- electronic or cryptographic signatures
- flattening completed PDFs
- compatibility changes for the other real-world PDF fixtures
- AI, Nemotron, voice, authentication, persistence, or database functionality

# Milestone 5 — Nemotron integration

...

# Milestone 6 — Form agent

...

# Milestone 7 — Voice

...

# Milestone 8 — Full workflow

...

# Milestone 9 — Polish and reliability

...

# Milestone 10 — Deployment

...

# Milestone 11 — Hackathon submission
