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

## North star experience

The finished product is conversation-first, not a traditional form builder.

The intended user experience is:
1. The user uploads a fillable PDF.
2. The PDF remains the main visual surface.
3. A voice-first assistant guides the user through one relevant question at a time.
4. The user can speak or type, ask for an explanation, skip a question, or correct an answer.
5. The assistant converts the user's own answer into a structured proposed field update.
6. The user confirms or edits every AI-proposed factual value before it is applied.
7. The confirmed value updates the same live PDF preview used by manual editing.
8. The user reviews unanswered and completed fields before downloading the final PDF.

Final interface hierarchy:
- primary: voice and text conversation with the form assistant
- secondary: click a field on the displayed PDF to inspect or edit it directly
- fallback: an "Edit all fields" drawer containing the existing manual controls

The manual controls remain valuable as a fallback, accessibility option, review
surface, and development tool. They must not be the mechanism the AI operates.
Voice, text, direct PDF edits, and manual controls must all update the same
canonical field state through stable field IDs.

Core safety and state rules:
- the user is the source of factual information
- the AI may explain, clarify, format, and propose; it must not invent facts
- AI-proposed field changes require explicit user confirmation
- an explicit manual or direct-on-form edit counts as user confirmation
- only confirmed values are sent to the PDF filling service
- the Form Agent returns structured proposals and never edits PDF bytes directly
- the PDF Service remains independent from AI and voice functionality

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

---

# Milestone 4.6 — SBA startup-cost worksheet compatibility

Status: COMPLETE

Goal:
Reliably extract, edit, preview, and download the bundled SBA Startup Costs
Worksheet through the existing PDF workflow.

Acceptance criteria:
- extraction returns the worksheet's 93 user-editable fields
- the 31 expense-description fields retain their existing text values
- the 62 editable currency fields retain their existing values and use numeric UI controls
- the five calculated total fields are not exposed as user-editable inputs
- all 93 editable fields can be submitted in one fill request
- submitted currency values are validated without executing PDF JavaScript
- the worksheet's five standard sum totals are recalculated by the PDF service
- updated currency and total appearances use the worksheet's two-decimal formatting
- the generated PDF remains interactive and retains its form actions
- the original SBA fixture remains unchanged
- a rendered populated worksheet is visually legible and shows correct totals
- existing backend tests pass
- frontend production build passes

Do not implement:
- arbitrary PDF JavaScript execution
- SBA-specific business advice or financial guidance
- flattening completed PDFs
- compatibility changes for the other real-world PDF fixtures
- AI, Nemotron, voice, authentication, persistence, or database functionality

---

# Milestone 4.7 — Question-aligned field UI

Status: COMPLETE

Goal:
Make the manual input controls correspond clearly to the questions and visual
order of the uploaded PDF.

Acceptance criteria:
- extraction returns a user-facing label and one-based page number for each field
- a meaningful AcroForm alternate name (`/TU`) is used as the field label
- blank or placeholder alternate names such as `undefined` fall back to a humanized field ID
- fields are returned in page order and approximately top-to-bottom, left-to-right order
- fields on the same visual row are ordered left-to-right
- a field with repeated widgets appears once at its earliest visual position
- the frontend groups controls by PDF page
- the frontend displays the extracted label while retaining the internal field ID as secondary text
- the synthetic household-support fixture's controls follow its visible question order
- existing extraction and filling behavior remains unchanged
- backend tests pass
- frontend production build passes

Do not implement:
- OCR or coordinate-based extraction of nearby page text
- custom PDF viewing or automatic preview scrolling
- AI-generated labels or question interpretation
- changes to PDF filling behavior
- AI, Nemotron, voice, authentication, persistence, or database functionality

---

# Milestone 4.8 — Custom page preview

Status: COMPLETE

Goal:
Replace the browser's native PDF viewer with a focused, visually consistent
page preview for the existing manual form workflow.

Acceptance criteria:
- the selected original PDF is rendered without the browser's native PDF controls
- the latest successfully filled PDF replaces the original in the same custom preview
- one PDF page is displayed at a time and scales to the available preview width
- previous and next controls navigate between pages
- the current page and total page count are visible
- navigation controls are disabled at the first and last page boundaries
- the current page is retained when a live filled preview replaces the original, when valid
- PDF loading and rendering errors are shown inside the preview
- the existing extraction, live filling, and download workflows remain unchanged
- frontend production build passes
- existing backend tests pass

Do not implement:
- direct PDF editing or annotation in the preview
- thumbnail navigation, search, zoom, rotation, or fullscreen controls
- text selection or custom form controls overlaid on the PDF page
- automatic navigation from a form field to its PDF page
- OCR or page-text extraction
- backend PDF rendering changes
- AI, Nemotron, voice, authentication, persistence, or database functionality

# Milestone 5 — Nemotron integration

Status: COMPLETE

Goal:
Connect the backend to NVIDIA Nemotron through Nebius Token Factory and use it
to explain one known PDF field in plain language.

Acceptance criteria:
- Nebius credentials are read from environment variables and never exposed to the frontend
- the Nemotron Service is the only component that communicates with Nebius
- a backend endpoint accepts a known field's label, type, options, and limited form context
- the response explains the question without proposing or applying a field value
- the prompt explicitly prohibits invented personal facts and unsupported legal or financial advice
- provider failures return a controlled API error
- backend tests mock the Nemotron Service and require no network access
- existing PDF tests and frontend production build pass

Do not implement:
- multi-turn agent orchestration
- field updates or automatic PDF filling
- voice input or output
- direct-on-form editing
- authentication, persistence, or a database

# Milestone 5.1 — In-app AI field explainer

Status: COMPLETE

Goal:
Make the existing Nemotron field-explanation capability visible and usable in
the current PDF workflow.

User flow:
- upload and extract a fillable PDF through the existing workflow
- choose "Explain with AI" for one extracted field
- send that field's ID, label, type, options, and limited page context to POST /ai/explain
- display the returned explanation in a focused assistant panel beside the PDF
- choose another field and request a new explanation when needed

Acceptance criteria:
- every supported extracted field has an "Explain with AI" action
- only one field is selected for explanation at a time
- only bounded metadata for the selected field is sent to POST /ai/explain
- the raw PDF is not sent to Nemotron
- AI loading, success, retry, and error states are visible
- the returned explanation is displayed beside the PDF
- the UI identifies NVIDIA Nemotron via Nebius Token Factory as the AI provider
- requesting or receiving an explanation does not change any field value
- requesting or receiving an explanation does not trigger PDF filling
- the existing manual editing, live preview, and download workflows remain unchanged
- existing backend tests pass
- frontend production build passes

Do not implement:
- free-form questions or conversation
- answer proposals or AI-applied field values
- conversation history or agent orchestration
- voice input or output
- direct-on-form editing
- authentication, persistence, or a database

# Milestone 5.2 — Typed questions about a field

Status: COMPLETE

Goal:
Let the user ask one typed explanatory question about the currently selected
PDF field without introducing the full Form Agent.

User flow:
- select an extracted field in the assistant panel
- type a question about what that field means or what information to consult
- send the question with bounded metadata for the selected field to the backend
- display Nemotron's explanation in the assistant panel
- ask another independent question when needed

Acceptance criteria:
- the assistant panel provides a typed question input for the selected field
- the backend accepts one user question plus the selected field's ID, label, type, options, and limited context
- the Nemotron Service remains the only component that communicates with Nebius
- the prompt treats field content and the user's question as untrusted input
- responses explain the field but never select, propose, or apply a field value
- each request is independent and does not require server-side conversation state
- question submission, loading, response, retry, and error states are visible
- changing the selected field clears or clearly separates the previous field's response
- no AI response changes the shared field state or triggers PDF filling
- backend tests use mocked Nemotron responses and require no network access
- existing PDF tests pass
- frontend production build passes

Do not implement:
- multi-turn conversation history
- guided field progression or selection of the next field
- structured field proposals, confirmation, or AI-assisted filling
- voice input or output
- direct-on-form editing
- authentication, persistence, or a database

# Milestone 6.1 — Agent contract and validation

Status: COMPLETE

Goal:
Create the backend Form Agent boundary and a validated structured action
contract without changing the frontend workflow.

Acceptance criteria:
- Form Agent logic lives in a separate service from the PDF Service and Nemotron Service
- a backend endpoint accepts the extracted field schema, confirmed field state, optional active field, current user message, and bounded conversation context
- the Form Agent can return a structured explain, clarify, propose, skip, or next action
- every action follows a documented response schema
- every proposal contains a field ID and a value compatible with that field's type and available options
- backend code rejects unknown field IDs, unsupported field types, invalid option values, and malformed model output
- proposed values remain separate from confirmed values
- the Form Agent never edits PDF bytes or calls the PDF Service
- provider and validation failures return controlled API errors
- backend tests mock the Nemotron Service and require no network access
- existing PDF tests pass

Do not implement:
- frontend conversation UI
- applying or confirming proposed values
- voice input or output
- direct editing on the rendered PDF page
- authentication, persistence, or a database

# Milestone 6.2 — Conversation and guided progression

Status: COMPLETE

Goal:
Add a typed conversation that remembers a bounded recent exchange, keeps an
active field, and guides the user through unanswered fields.

Acceptance criteria:
- the frontend provides a typed conversation interface for the Form Agent
- conversation state remains ephemeral in the browser
- at most the eight most recent user and assistant messages are sent with each request
- follow-up questions can refer to recent messages about the active field
- explanations and clarifications keep the same field active
- the agent can select the first unanswered supported field
- skipping or resolving a field allows the agent to select the next unanswered supported field
- explain, clarify, skip, next, and proposal responses are visibly distinguished
- any proposal returned during this milestone remains unconfirmed and cannot update a field or PDF
- conversation loading, retry, and controlled error states are visible
- changing forms clears the active field and conversation state
- backend tests use a mocked Nemotron Service
- frontend production build and existing backend tests pass

Do not implement:
- proposal confirmation or AI-assisted PDF filling
- voice input or output
- direct editing on the rendered PDF page
- unbounded or server-persisted conversation history
- authentication, persistence, or a database

# Milestone 6.3 — Proposal and confirmation

Status: NOT STARTED

Goal:
Allow the Form Agent to propose a field value and let the user explicitly
confirm, edit, reject, or skip it before any PDF update occurs.

Acceptance criteria:
- the proposal UI clearly displays the target field and proposed value
- proposed values remain separate from confirmed values in canonical frontend state
- unknown field IDs and values incompatible with the field type or options are rejected outside the model
- the user can confirm, edit, reject, or skip each proposal
- ambiguous conversational replies never count as confirmation
- only an explicit confirmation or user edit moves a proposal into confirmed field state
- rejecting a proposal leaves the confirmed field value unchanged
- skipping a field records it as skipped without assigning a value
- confirmed proposals update the shared field state used by the existing manual controls
- confirmed proposals trigger the existing PDF filling flow and visible live preview
- backend tests use a mocked Nemotron Service
- frontend production build and existing backend tests pass

Do not implement:
- voice input or output
- direct editing on the rendered PDF page
- autonomous submission or download
- authentication, persistence, or a database

# Milestone 6.4 — Conversation-first UI

Status: NOT STARTED

Goal:
Make the typed Form Agent the primary workspace while preserving manual editing
as an accessible fallback.

Acceptance criteria:
- the conversation is the primary interface beside the PDF preview
- the currently active field and progress through supported fields are visible
- the existing manual field controls move into an "Edit all fields" drawer
- the manual drawer is collapsed by default and can be opened at any time
- conversation proposals, confirmed agent values, and manual edits use the same canonical field state
- moving between conversation and manual editing does not lose values or conversation state
- manual edits continue to count as explicit user confirmation
- the existing live PDF preview and download workflow remain available
- loading and error states remain visible when the manual drawer is closed
- frontend production build and existing backend tests pass

Do not implement:
- voice input or output
- direct editing on the rendered PDF page
- autonomous submission
- authentication, persistence, or a database

# Milestone 7 — Voice

Status: NOT STARTED

Goal:
Add speech as an interface around the working typed Form Agent without creating
a separate voice-specific reasoning path.

Acceptance criteria:
- the user can deliberately start and stop voice capture
- recognized speech is displayed as an editable transcript before or while it is submitted
- the transcript uses the same Form Agent endpoint and confirmation flow as typed text
- assistant responses can be spoken while remaining visible as text
- microphone permission, listening, processing, retry, and failure states are clear
- the user can always fall back to typing
- stopping or cancelling voice input does not change a form field

Do not implement:
- always-on recording or wake-word detection
- voice-controlled confirmation without a visible confirmation state
- a separate voice agent or duplicate form state
- authentication, persistence, or a database

# Milestone 8 — Full workflow

Status: NOT STARTED

Goal:
Connect conversation, direct PDF interaction, review, filling, and download into
the north star experience.

Acceptance criteria:
- extraction exposes the widget geometry required to associate visible PDF fields with stable field IDs
- the active assistant question navigates to and highlights its PDF page and field when geometry is available
- clicking a supported field on the PDF opens a focused edit control for that field
- direct edits, manual edits, and confirmed agent proposals use the same canonical frontend field state
- the manual "Edit all fields" drawer is closed by default but remains available
- the user can move between conversation, direct editing, and manual editing without losing values
- the user can review completed, unanswered, skipped, and proposed fields
- only confirmed values are included in generated PDFs
- the final reviewed PDF can be downloaded through the existing backend filling flow

Do not implement:
- client-side PDF mutation
- free-form annotation or drawing
- support for non-AcroForm PDFs, XFA, OCR, or online forms
- autonomous form submission
- authentication, persistence, or a database

# Milestone 9 — Polish and reliability

Status: NOT STARTED

Goal:
Make the complete hackathon workflow reliable, accessible, understandable, and
demo-ready across the supported fixtures.

Acceptance criteria:
- keyboard and screen-reader flows work for conversation, confirmations, PDF navigation, and the manual drawer
- responsive layouts work on laptop and mobile-sized screens
- users can undo or correct confirmed answers before download
- loading, retry, offline, microphone, model, extraction, and filling errors have clear recovery paths
- unsupported fields and documents are explained without losing the uploaded PDF
- the supported demo fixtures complete successfully from upload through download
- frontend and backend automated checks pass

# Milestone 10 — Deployment

Status: NOT STARTED

Goal:
Deploy the frontend and backend with secure configuration suitable for the
hackathon demonstration.

Acceptance criteria:
- frontend and backend are reachable over HTTPS
- production CORS is restricted to the deployed frontend
- Nebius credentials remain server-side
- health checks and essential logs are available
- file-size and request-time limits fail clearly
- no user document persistence is introduced without an explicit decision

# Milestone 11 — Hackathon submission

Status: NOT STARTED

Goal:
Package a clear, repeatable demonstration of the conversation-first form
assistant and its required NVIDIA/Nebius technology.

Acceptance criteria:
- the demo shows upload, explanation, voice or typed guidance, confirmation, live PDF update, review, and download
- the submission clearly identifies Nemotron and Nebius Token Factory usage
- setup and local-run documentation is current
- architecture and safety boundaries are explained
- the demo has a tested fallback path if microphone access or an external API is unavailable
