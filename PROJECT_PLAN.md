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
6. When safe formatting changes visible text, the interface shows the user's
   original answer beside the value prepared for the form and explains the
   transformation.
7. The user confirms, edits, uses the original, or rejects every AI-proposed
   factual value before it is applied.
8. The confirmed value updates the same live PDF preview used by manual editing.
9. The user reviews unanswered and completed fields before downloading the final PDF.

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
- the assistant's natural-language message is separate from the typed effect
  that may change conversation or form state
- safe formatting preserves the original answer and remains reviewable
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

## Current implementation status

- the typed guided interview, human-helper voice interview, hands-free
  interruption, and voice-first workspace redesign are complete through
  Milestone 7.6
- the automated conversation evaluation harness, live baseline, and targeted
  evidence-gated voice-like reliability passes are complete through Milestone
  7.4; human-helper experience measurement is complete through Milestone 7.7
- Milestone 7.8 targeted human-helper conversation repairs is complete; the
  unchanged fixed human-helper suite passes both its correctness and
  human-helper gates
- Milestone 8 full workflow is complete: normalized widget geometry, active
  field navigation, direct PDF editing, canonical cross-mode state, final
  review, confirmed-only filling, and download are connected
- Milestone 9 polish and reliability is complete: accessibility, responsive
  layout, non-destructive recovery, correction, and the supported-fixture
  workflow are covered by focused checks and the full regression suite
- Milestone 9.2 Deepgram streaming and Milestone 9.2.1 Nemotron-first
  orchestration are implemented but still require their recorded live/manual
  completion evidence
- Milestone 9.2.2 context-rich natural conversation and proposal review is
  implemented with automated regression coverage and a passing configured-model
  comparison; its browser/Deepgram manual evidence is still pending
- Milestone 9.2.3 continuous hands-free voice is implemented with automated
  session, silence, recovery, interruption-transfer, cleanup, and regression
  coverage; its real-browser acoustic and ten-turn evidence is still pending
- the immediate remaining work is Milestone 9.2.3 live/manual evidence,
  followed by Milestones 9.2.4 and 9.2.5: a fixed-viewport workspace and an
  integrated human-helper gate
- deployment has not started; persistence remains outside the current plan

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

# Milestone 6.2.1 — Conversation quality and grounding

Status: COMPLETE

Goal:
Make the guided conversation natural and grounded in the available form schema
before adding proposal confirmation.

Acceptance criteria:
- a next action asks the selected field using its real label, type, and available options
- next-action responses never repeat start or continue navigation commands
- the agent treats the ordered field schema as its only form-wide context
- questions about why an organisation requests information do not produce an invented purpose
- when the schema does not contain an authoritative purpose, the response says so and directs the user to official instructions or the form owner
- placeholder dropdown choices such as `Select one` are treated as unanswered and are not offered as real answers
- proposal responses explicitly say that the value is awaiting confirmation
- proposed values remain separate from confirmed values and cannot update a field or PDF
- one invalid structured model action receives at most one correction attempt before a controlled error
- backend tests use a mocked Nemotron Service and require no network access
- frontend production build and existing backend tests pass

Do not implement:
- confirming, rejecting, editing, or applying an AI proposal
- AI-assisted PDF filling
- raw PDF or page-text transmission to Nemotron
- voice input or output
- direct editing on the rendered PDF page
- authentication, persistence, or a database

# Milestone 6.3 — Proposal and confirmation

Status: COMPLETE

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

Status: COMPLETE

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

# Milestone 6.5 — Document-aware field questions

Status: COMPLETE

Goal:
Ground each supported AcroForm field in the visible question and instructions
from the PDF's native text layer before that context reaches the Form Agent.

Acceptance criteria:
- native page text is extracted with PyMuPDF without OCR
- widget geometry is used internally to associate fields with nearby visible text
- extraction returns structured question, nearby help text, section, and page context when confidently available
- existing stable field IDs, types, options, values, ordering, and filling behavior remain unchanged
- ambiguous text associations fall back to existing labels rather than inventing a question
- extracted document text and metadata are treated as untrusted data
- raw PDF bytes are never sent to Nemotron
- unconfirmed widget values are not included as form instructions or question context
- sample, household-support, USCIS I-9, and SBA fixtures have deterministic grounding tests
- existing backend tests and frontend production build pass

Do not implement:
- OCR or support for image-only or scanned questions
- support for non-AcroForm PDFs or XFA
- AI-generated questions, labels, instructions, or purposes
- exposing widget geometry for direct editing, highlighting, or PDF navigation
- changes to PDF filling behavior
- voice interaction
- authentication, persistence, or a database

# Milestone 6.6 — Multi-form conversation hardening

Status: COMPLETE

Goal:
Use structured document context and systematic evaluations to make typed guided
completion reliable across the supported fixtures before adding voice.

Acceptance criteria:
- Form Agent requests include bounded form title and instructions, a compact ordered question summary, and detailed active-field context
- full-form context is structured and size-bounded rather than a raw PDF or page-text dump
- the active question uses grounded question metadata when available and the existing label fallback otherwise
- prompts distinguish trusted system rules from untrusted extracted document text, field metadata, and user content
- prompts never infer missing personal facts or unsupported reasons why a form requests information
- dropdown, checkbox, numeric, and text answers produce type-compatible proposals or a clarification request
- next-field progression, follow-up explanation, skip, proposal, and confirmation boundaries continue to work across supported fixtures
- deterministic mocked scenarios cover the sample, household-support, USCIS I-9, and SBA fixtures
- evaluations measure grounded question selection, valid action and proposal rates, and invented-fact or invented-purpose failures
- an optional live Nemotron evaluation can use environment credentials but is excluded from the normal offline test suite
- existing backend tests and frontend production build pass

Do not implement:
- OCR
- sending raw PDF bytes or unbounded page text to Nemotron
- unbounded conversation history
- automatic confirmation, application, or invention of user answers
- direct editing or highlighting on the rendered PDF
- voice interaction
- legal or financial advice
- authentication, persistence, database, or a new agent framework

# Milestone 6.7 — Typed conversation reliability

Status: COMPLETE

Goal:
Make typed form completion feel conversational and reliably convert clear user
answers into valid, reviewable proposals before adding voice.

Acceptance criteria:
- starting, continuing, and explicitly skipping the active field are handled deterministically without relying on model-selected navigation
- unambiguous natural-language checkbox, dropdown, and numeric answers can be normalized against the active field schema without inventing information
- deterministic answer handling never treats an explanatory question as a factual answer
- model-proposed checkbox, dropdown, and numeric values are safely canonicalized when their meaning is unambiguous
- an invalid model proposal produces a field-specific clarification instead of exposing an invalid-proposal error or silently advancing
- clarification responses explain what could not be matched and show the accepted answer shape or available options rather than merely repeating the same question
- next, skip, proposal, confirmation, rejection, and correction messages use concise conversational language grounded in the active field
- confirming, editing, rejecting, or skipping a proposal preserves the existing explicit-confirmation boundary and gives visible conversational feedback
- field-value normalization and validation live in a focused module separate from Form Agent orchestration and PDF manipulation
- deterministic evaluations cover natural-language answers, invalid proposal recovery, skip reliability, and question-versus-answer boundaries across supported field types
- existing backend tests, the offline Form Agent evaluation, and the frontend production build pass

Do not implement:
- a second model or multi-agent workflow unless evaluations demonstrate a need
- automatic confirmation or application of proposed values
- OCR, raw PDF transmission to Nemotron, or changes to PDF extraction or filling
- voice input or output
- direct editing or highlighting on the rendered PDF
- legal or financial advice
- authentication, persistence, database, or an agent framework

# Milestone 6.8 — Modular Form Agent internals

Status: COMPLETE

Goal:
Split the remaining Form Agent implementation into focused internal modules
without changing its public API or user-visible behaviour.

Intended structure:
- `models.py` owns request, response, field, action, and conversation-state schemas
- `orchestrator.py` coordinates one agent turn
- `conversation_policy.py` owns deterministic routing and state-transition policy
- `prompt_builder.py` prepares bounded, injection-resistant model context
- `response_parser.py` parses, canonicalizes, and validates model output
- `value_normalizer.py` contains the existing deterministic field-value logic

Acceptance criteria:
- Form Agent code lives in a dedicated backend package with the listed responsibilities separated clearly
- FastAPI depends on one public Form Agent service boundary rather than importing internal modules directly
- the Nemotron Service remains the only component that communicates with Nebius
- the PDF Service remains independent from every Form Agent module
- existing request and response payloads remain compatible during this refactor
- prompt construction, response parsing, conversation policy, and value normalization can be tested independently
- circular imports and duplicated field-value validation are not introduced
- existing backend tests, offline evaluation, optional live evaluation, and frontend production build continue to pass

Do not implement:
- new conversation behaviour or UI changes
- a second model, multi-agent orchestration, or an agent framework
- voice, OCR, PDF changes, authentication, persistence, or a database

# Milestone 6.9 — Explicit conversation state machine

Status: COMPLETE

Goal:
Replace inferred conversation phases with an explicit, validated state machine
shared by the frontend and backend.

Conversation phases:
- asking a question
- awaiting an answer
- awaiting clarification
- awaiting proposal confirmation
- field confirmed
- field skipped
- form complete

Acceptance criteria:
- the agent contract contains a typed conversation phase and active field state
- an awaiting-confirmation state includes the pending field ID and proposed value
- each response declares the resulting phase instead of requiring the frontend to infer it from message text
- allowed transitions are defined centrally and covered by backend tests
- invalid or stale transitions return a controlled error without changing confirmed form state
- ordinary typed replies cannot confirm a proposal; confirmation remains a distinct explicit user event
- messages received while awaiting confirmation cannot create a duplicate proposal for the same answer
- rejection returns the active field to an answerable state without losing confirmed values
- skipped, confirmed, and completed fields cannot accidentally become active through a model action
- state remains ephemeral and is sent explicitly with bounded requests; no server persistence is introduced
- frontend and backend use the same canonical phase names and pending-proposal contract
- existing confirmation safety, PDF filling, and live-preview behaviour remain unchanged
- backend tests, state-transition tests, offline evaluation, and frontend production build pass

Do not implement:
- automatic confirmation from conversational phrases such as `yes` or `looks good`
- automatic progression to the next field
- voice, authentication, persistence, a database, or a second model

# Milestone 6.10 — Transcript-level agent evaluation

Status: COMPLETE

Goal:
Measure complete multi-turn form-completion behaviour rather than evaluating
only isolated agent responses.

Acceptance criteria:
- deterministic transcript fixtures cover complete conversations across the sample, household-support, USCIS I-9, and SBA forms
- transcripts include ask, unclear answer, clarification, proposal, rejection, correction, confirmation, skip, next-field, and completion paths
- state transitions and confirmed values are asserted after every turn
- evaluation reports form completion rate
- evaluation reports first-attempt accepted-proposal rate
- evaluation reports average turns per confirmed field
- evaluation reports repeated-question rate and clarification rate
- evaluation reports invalid-action and confirmation-boundary failure rates
- optional live evaluation reports latency and model calls per field
- invented-fact and invented-purpose failures remain explicit zero-tolerance metrics
- normal automated tests use deterministic model doubles and never require network access
- optional live transcripts use environment credentials and are excluded from the normal test suite
- evaluation output identifies the exact transcript and turn for every failure

Do not implement:
- prompt tuning solely to make scripted answers pass
- a second model or fallback model
- production analytics, user tracking, persistence, or a database

# Milestone 6.11 — Field-type answer adapters

Status: COMPLETE

Goal:
Convert common conversational answers into form-compatible proposals through
focused, independently tested field-type adapters.

Initial adapters:
- names and free text
- dates
- money and general numbers
- yes/no and checkbox answers
- dropdown options
- addresses
- postcodes
- phone numbers

Acceptance criteria:
- adapters share a small result contract for matched value, clarification needed, or not applicable
- every clarification result includes a specific user-facing reason and accepted answer shape
- adapter selection uses deterministic field metadata and conservative semantic hints
- adapters preserve the user's factual meaning and never supply missing personal information
- ambiguous dates, numbers, addresses, and option matches request clarification rather than guessing
- locale-sensitive formats are preserved or clarified when locale cannot be established safely
- dropdown proposals always resolve to an exact available option
- money proposals separate harmless display characters from the stored numeric value
- phone numbers and postcodes are not reformatted destructively when the required format is unknown
- free-text normalization removes conversational framing only when the intended value is unambiguous
- the model remains available for ambiguous interpretation but cannot bypass adapter validation
- adapter tests include positive, negative, ambiguous, negated, and adversarial examples
- transcript evaluation demonstrates fewer repeated questions and invalid proposals without increasing invention failures
- existing backend tests and frontend production build pass

Do not implement:
- external address, identity, or phone-number verification
- geocoding or enrichment of user-supplied facts
- legal or eligibility validation
- a second model, voice, authentication, persistence, or a database

# Milestone 6.12 — Confirmation-driven progression

Status: COMPLETE

Goal:
Make the conversation progress naturally after an explicit proposal decision
without requiring a separate Continue action after every field.

Acceptance criteria:
- explicit confirmation applies the proposed value through the existing canonical field state
- confirmation produces a concise acknowledgement and deterministically asks the next unanswered field
- confirming an edited proposal follows the same transition and progression path
- rejection acknowledges that no value was applied and immediately invites a corrected answer for the same field
- skipping acknowledges the skipped field and deterministically asks the next unanswered field
- completing or skipping the final supported field transitions to form complete
- progression uses state-machine events rather than fabricated user messages
- automatic progression does not make an additional model call when the next question can be generated from field context
- rapid or repeated confirmation events cannot apply a proposal twice or skip multiple fields
- confirmed values trigger the existing PDF fill and live-preview workflow exactly once per accepted change
- the user can still pause, inspect the PDF, edit manually, or return to an earlier field
- transcript tests cover confirm, edit-confirm, reject-correct, skip, duplicate-event, and final-completion flows
- backend tests, transcript evaluation, and frontend production build pass

Do not implement:
- conversational or voice-only confirmation
- automatic acceptance of model proposals
- autonomous submission or download
- voice, authentication, persistence, or a database

# Milestone 6.13 — Official instruction grounding

Status: COMPLETE

Goal:
Ground explanations in bounded, attributable instructions from approved official
sources when those instructions are available for a supported form.

Acceptance criteria:
- official guidance sources are explicitly allowlisted per supported form and version
- each source records its title, issuing organisation, source URL, form version, and retrieval date
- guidance is stored as small local structured resources suitable for the hackathon build
- relevant excerpts are selected by form, field, and section without a vector database or retrieval framework
- only bounded relevant excerpts are included in Form Agent context
- official excerpts, like PDF text and user input, are treated as untrusted model data
- responses distinguish official guidance from the assistant's plain-language explanation
- the UI displays the source title and link when official guidance informed an answer
- when no relevant official guidance is available, the assistant says so rather than inferring a purpose or rule
- quoted or paraphrased guidance remains traceable to its source and version
- tests cover correct source selection, missing guidance, mismatched form versions, prompt injection inside source text, and bounded context
- no guidance source can provide or confirm the user's personal factual answer
- existing safety, agent, PDF, and frontend checks pass

Do not implement:
- runtime web crawling or unrestricted internet retrieval
- a vector database, embedding service, or general RAG framework
- legal, financial, medical, or eligibility advice
- automatic form-version substitution
- voice, authentication, persistence, or a database

# Milestone 6.13.1 — Policy-gated web guidance with Tavily

Status: COMPLETE

Goal:
Use Tavily to find current, attributable web guidance when reviewed local
guidance is insufficient, while preserving the existing privacy, grounding,
and confirmation boundaries.

User flow:
- the user asks a normal explanatory question about the active field
- reviewed local guidance remains the first source when it answers the question
- when local guidance is insufficient and the request meets a deterministic
  lookup policy, the backend performs a bounded Tavily search
- the backend builds the search query from non-personal form and field metadata
  plus a controlled explanation topic
- Nemotron produces a concise plain-language explanation from bounded search
  results
- the UI labels Tavily material as live web guidance, links every source, and
  offers a manual search or retry control when appropriate

Intended architecture:
- Tavily is a retrieval tool inside the existing Form Agent turn; it is not a
  second agent, a separate chat workflow, or a frontend integration
- the frontend continues to call the existing Form Agent endpoint and never
  communicates with Tavily directly
- the Form Agent orchestrator validates the conversation event and checks
  reviewed local guidance before considering live lookup
- a small deterministic web-guidance policy classifies eligible informational
  questions and builds the bounded non-personal search query
- the dedicated Tavily Service owns credentials, HTTP transport, timeouts, and
  provider-response parsing, but owns no conversation or PDF logic
- a web-guidance module validates, deduplicates, ranks, labels, and bounds Tavily
  results before they can enter the existing prompt builder
- the prompt builder places normalized web snippets inside the existing
  untrusted-context boundary alongside form and user text
- Nemotron returns the existing typed explanation action; Tavily cannot return
  an agent action or bypass the response parser
- web-source citations are returned as typed response metadata and do not alter
  conversation phase, proposal state, confirmed values, or PDF bytes
- an eligible turn makes at most one Tavily request; any subsequent Nemotron
  call follows the existing structured-output correction limit, and lookup
  failure does not trigger recursive searches or an unnecessary model call

Acceptance criteria:
- the Tavily API key is read from `TAVILY_API_KEY` and remains server-side
- a dedicated Tavily Service is the only component that communicates with the
  Tavily API
- Tavily is integrated through the existing Form Agent endpoint and
  orchestrator rather than through a second public workflow
- the implementation uses the existing HTTP client rather than adding an agent
  framework or Tavily SDK without a demonstrated need
- live lookup does not require a preconfigured issuer-domain allowlist or an
  already recognized form ID
- a deterministic backend policy, not the model, decides whether an
  explanatory request qualifies for web lookup
- lookup is triggered only by an informational user request when reviewed local
  guidance is insufficient; it never runs for ordinary answers, confirmations,
  navigation, or background prefetching
- search queries are constructed server-side and contain no PDF bytes, entered
  field values, proposed values, personal answers, or conversation history
- queries use bounded form title, version when available, issuing organisation
  when available, active-field question, and a controlled topic such as meaning,
  instructions, or where to find the requested information
- Tavily-generated answers and raw page content are disabled; only a small
  bounded set of titled result snippets and URLs is accepted
- result count, per-result text, and total live-guidance context have fixed
  limits before content can reach Nemotron
- returned URLs must use public HTTPS endpoints; private, local, malformed,
  duplicate, and unsupported URLs are discarded
- source selection prefers relevant primary and issuing-organisation material,
  but general search results are never presented as reviewed or official merely
  because Tavily returned them
- claims about requirements or rules require clear source support; conflicting,
  weak, or uncertain results produce an uncertainty message and source links
  rather than a definitive answer
- Tavily result text is treated as untrusted model data and cannot provide,
  propose, confirm, or apply the user's personal factual answer
- Nemotron remains the only model and produces a grounded explanation from the
  bounded live results through the existing Form Agent safety rules
- the response identifies that Tavily performed the lookup and includes source
  title, URL, retrieval time, and form version when known for every result used
- the UI clearly distinguishes live web guidance from reviewed official guidance
  and provides visible searching, success, empty-result, retry, and error states
- unavailable credentials, timeouts, authentication failures, rate limits,
  empty results, and invalid provider responses return controlled errors without
  blocking manual form completion
- mocked backend tests require no network access and cover policy gating,
  post-response URL validation, privacy boundaries, source-quality labeling,
  conflicting results, prompt injection in result text, context bounds,
  attribution, and provider failures
- an optional live smoke test demonstrates one web-guidance lookup without
  becoming part of the default test suite
- existing safety, agent, PDF, transcript-evaluation, and frontend checks pass

Do not implement:
- autonomous tool selection or background search chosen by the model
- proactive search before the user asks an informational question
- presenting general web results as reviewed official guidance
- news or image search
- Tavily Crawl, Extract, Research, or general browsing tools
- transmission of uploaded PDFs, field values, personal answers, or conversation
  history to Tavily
- automatic replacement of reviewed local guidance with live results
- legal, financial, medical, tax, or eligibility advice
- a vector database, embeddings, general RAG framework, or agent framework
- caching, persistence, authentication, voice, or a database
- new PDF-format compatibility or new recognized forms

# Milestone 6.13.2 — Live-guidance relevance gate

Status: COMPLETE

Goal:
Prevent unrelated Tavily results from entering the Nemotron prompt or being
presented as evidence for an explanation.

Acceptance criteria:
- every Tavily result passes a deterministic relevance check before ranking,
  prompt construction, or source attribution
- relevance uses only bounded form identity, issuer, version, active-field
  question, and controlled explanation-topic metadata
- a result must match the target form or issuer when known, or contain a strong
  combination of form-specific and active-question evidence when identity is
  unavailable
- generic terms such as `name`, `address`, `application`, or `form` cannot make
  an otherwise unrelated result relevant
- results about another form, agency, jurisdiction, benefit, or process are
  discarded even when they share a field label
- discarded results never reach Nemotron and never appear as response citations
- an empty relevant-result set remains a normal typed outcome for the
  orchestrator rather than a provider or parsing error
- reviewed local guidance remains preferred and bypasses Tavily when sufficient
- tests reject the unrelated IRS, Department of Labor, and housing results seen
  during the sample and household-support demo flows
- tests retain clearly relevant IRS W-9 results and preserve the existing local
  USCIS I-9 guidance path
- mocked backend tests require no network access, and the optional live smoke
  test reports how many returned results passed the relevance gate
- existing safety, agent, PDF, transcript-evaluation, and frontend checks pass

Do not implement:
- model-based source ranking or a second model call to judge relevance
- a mandatory global domain allowlist
- embeddings, a vector database, Tavily Crawl or Extract, or a general RAG
  framework
- changes to proposal confirmation, PDF filling, voice, authentication,
  persistence, or a database

# Milestone 6.13.3 — Deterministic insufficient-guidance response

Status: COMPLETE

Goal:
Return a safe, useful, deterministic response when neither reviewed local
guidance nor relevant live evidence can answer the user's informational
question.

Acceptance criteria:
- the orchestrator identifies insufficient guidance before prompt construction
  when no relevant evidence remains after validation
- insufficient guidance returns a typed explanation response without calling
  Nemotron
- the response clearly says that the available form schema and verified
  guidance do not establish the requested meaning, purpose, or rule
- the response may direct the user to the form's own instructions, issuing
  organisation, or another clearly identified official source without claiming
  what that source will say
- deterministic wording never invents a purpose involving identity matching,
  records, benefits, eligibility, legal requirements, or administrative need
- the active field and conversation phase remain unchanged so the user can
  answer, skip, retry guidance, or continue manually
- irrelevant discarded sources are not displayed as supporting citations
- Tavily unavailability and insufficient relevant evidence remain distinct
  typed outcomes with clear recovery messages
- regression tests cover the generic sample form and the fictional
  household-support form and assert that Nemotron is not called
- transcript evaluation keeps invented-purpose and invented-fact failures at
  zero for insufficient-guidance turns
- existing safety, agent, PDF, and frontend checks pass

Do not implement:
- guessing from general knowledge or asking Nemotron to soften an unsupported
  explanation
- legal, financial, medical, tax, benefit, or eligibility advice
- changes to ordinary answer interpretation or field proposals
- voice, authentication, persistence, or a database

# Milestone 6.13.4 — Claim-scoped source conflict detection

Status: COMPLETE

Goal:
Report conflicts only when relevant sources make incompatible claims about the
same active field, form version, and requested topic.

Acceptance criteria:
- conflict detection runs only over results that passed the live-guidance
  relevance gate
- each comparison is scoped to the active field and controlled topic, including
  definition, purpose, requiredness, accepted values, or formatting
- words such as `required` and `optional` conflict only when their surrounding
  claims refer to the same target field and form context
- a statement about a different line, section, field, form, or version cannot
  mark the active-field evidence as conflicting
- the detector produces a typed evidence status such as supported, limited,
  conflicting, or unavailable with a deterministic reason
- truly incompatible relevant claims still produce an uncertainty response and
  attributable source links rather than a definitive rule
- the IRS W-9 line 1 scenario is no longer marked conflicting because another
  snippet describes a different optional line
- tests cover same-field conflicts, different-field requiredness language,
  mismatched versions, duplicate paraphrases, and unrelated snippet text
- conflict classification does not use an LLM and cannot alter conversation
  state, field proposals, or confirmed values
- existing safety, agent, PDF, transcript-evaluation, and frontend checks pass

Do not implement:
- general fact checking or source-truth arbitration
- model-based contradiction detection
- autonomous additional searches to resolve a conflict
- legal or eligibility conclusions
- voice, authentication, persistence, or a database

# Milestone 6.13.5 — Selectable AcroForm capability validation

Status: COMPLETE

Goal:
Determine during extraction whether checkbox, radio, and other button widgets
have usable selectable states before the UI or Form Agent treats them as
answerable fields.

Acceptance criteria:
- extraction inspects the effective field type, button flags, parent and child
  widgets, and normal appearance states for every AcroForm button field
- push buttons are not exposed as answerable form questions
- a checkbox is supported only when it has an off state and at least one usable
  non-off export state
- radio groups expose their real mutually exclusive options when they can be
  mapped safely; ambiguous groups are marked unsupported rather than converted
  to booleans
- extracted fields include a deterministic supported/editable capability and a
  concise reason when a control cannot be filled safely
- unsupported controls remain visible for transparency but are excluded from
  agent progression, editable manual controls, and `/pdf/fill` submissions
- the filling service validates submitted choice values against the same
  extracted export-state rules so extraction and filling cannot disagree
- the DS-11 `Selection` control is identified as unsupported or represented by
  its actual selectable group before the agent can propose `true`
- the sample, USCIS I-9, and existing supported checkbox/dropdown behavior
  remains unchanged
- tests cover missing appearance dictionaries, off-only widgets, multiple
  export states, inherited parent state, radio groups, and push buttons
- generated supported-choice PDFs are reopened to verify stored values and
  effective widget states
- existing backend tests and frontend production build pass

Do not implement:
- guessing a selectable state from nearby text
- flattening PDFs, executing PDF JavaScript, or supporting XFA
- DS-11 question-to-widget text alignment beyond the capability metadata
- AI, voice, authentication, persistence, or a database

# Milestone 6.13.6 — DS-11 field grouping and question alignment

Status: COMPLETE

Goal:
Make the bundled State Department DS-11 fixture present correctly grouped,
human-readable, fillable questions through the existing PDF and Form Agent
workflow.

Acceptance criteria:
- DS-11 widget parent/child relationships and repeated widgets are resolved into
  stable logical fields without duplicate questions
- passport book/card and regular/large-book controls are associated with their
  correct visible option labels and selectable-state capabilities
- `Applicant Last Name` is associated with the applicant-name question rather
  than the adjacent large-book explanatory text
- nearby help text is attached only when its geometry and section relationship
  are unambiguous; uncertain text falls back to the humanized field label
- question ordering follows the visible DS-11 page and section order
- unsupported buttons remain clearly identified and are skipped by guided agent
  progression without preventing manual completion of supported fields
- the extracted schema passes the same frontend and Form Agent validation used
  by the other fixtures, including removal of blank placeholder options
- representative supported text and choice fields can be filled, reopened with
  `pypdf`, and rendered with correct visible values
- a typed DS-11 transcript reaches a valid proposal for the first supported
  applicant field without a fill-time selectable-state error
- deterministic tests assert the corrected labels, questions, grouping,
  ordering, capabilities, and representative stored values
- the sample, household-support, USCIS I-9, SBA, and W-9 fixture behavior does
  not regress
- existing backend tests, transcript evaluation, and frontend production build
  pass

Do not implement:
- passport eligibility, legal guidance, application advice, or factual answers
  for the user
- electronic signatures, barcode generation, or PDF JavaScript execution
- broad compatibility work for unrelated PDF formats, XFA, or scanned forms
- OCR, voice, authentication, persistence, or a database

# Milestone 6.13.7 — Conversational Form Agent experience

Status: COMPLETE

Problem to solve:
The current typed assistant is safe and state-aware, but it often feels like a
form wizard presented as a chat. Too many ordinary messages are handled as
commands, field answers, or requests for external guidance. This can produce
canned replies, repeated questions, an unnecessary Tavily dependency for plain
wording clarification, and duplicated unavailable-guidance messages.

Adding voice before fixing this would create the same rigid experience through
a microphone. The typed assistant must first become a useful conversational
partner while preserving the existing field-validation and confirmation
boundaries.

Goal:
Make the existing Form Agent feel like a natural, context-aware assistant that
can discuss the active question, explain it in simpler language, handle
uncertainty, answer progress questions, and return smoothly to form completion.
Nemotron should be the conversational layer; deterministic code should remain
the authority over navigation, field state, tool use, proposals, and
confirmation.

Conversation principles:
- the user remains the source of every personal factual answer
- Nemotron may paraphrase, explain, ask a focused follow-up, summarize progress,
  and help format the user's stated information
- conversational help and form mutation are separate: a natural response may
  have no form-state effect
- deterministic commands and clear field answers should stay fast and reliable
  without requiring unnecessary model or web calls
- a field proposal remains typed, validated, visibly pending, and separate from
  confirmed state
- Tavily is an evidence tool for external facts, current rules, requirements,
  purposes, or information sources; it is not the general conversation engine
- one conversational interruption must not lose the active field, pending
  proposal, confirmed values, skipped fields, or recent context
- safety should constrain factual effects without making harmless conversation
  sound like an error message

Turn-routing design:
1. Explicit commands such as confirm, edit-confirm, reject, skip, next, and
   focus-field are handled deterministically through the existing state machine.
2. A clear answer to the active field is interpreted by the existing field-type
   adapters first and becomes a validated proposal awaiting confirmation.
3. A wording request such as `What does this mean?` or `Explain that more
   simply` is sent to Nemotron with bounded field and form context. It does not
   call Tavily merely to paraphrase text already present in the form schema.
4. An uncertain or incomplete answer such as `around summer 2019` produces one
   focused follow-up that identifies what is missing and never guesses the
   missing value.
5. A request about purpose, legal effect, requiredness, eligibility, official
   instructions, or where to obtain information uses reviewed local guidance
   first and the existing policy-gated Tavily path only when eligible.
6. A progress or navigation question such as `What have we completed?` or `Can
   we return to this later?` is answered from deterministic conversation and
   field state without web search.
7. After a non-mutating explanation or progress interruption, the assistant
   keeps the active field and offers a natural path back to answering it.

Intended backend shape:
- keep `POST /agent/respond` as the single public conversational endpoint
- keep one Form Agent and the existing direct Python orchestration; do not add a
  second agent or an agent framework
- extend deterministic conversation policy to distinguish commands, field
  answers, wording clarification, uncertainty, progress questions, and
  evidence-dependent questions before choosing a tool path
- use the existing non-mutating explanation action for conversational help
  unless implementation review demonstrates that one small typed conversational
  action is materially clearer
- give Nemotron bounded active-field context, a compact ordered form summary,
  current progress, and at most the existing bounded recent history
- add prompt modes with explicit turn objectives such as `paraphrase`,
  `clarify_answer`, `progress_help`, and `evidence_grounded_explanation`
- allow Nemotron to phrase conversational responses naturally, but continue to
  parse and validate every structured action outside the model
- keep backend policy, not Nemotron, responsible for deciding whether Tavily is
  called
- retain the current maximum of one initial model call and one structured-output
  correction attempt for a model-handled turn
- keep confirmation, PDF filling, and all canonical field-state changes outside
  Nemotron

Intended frontend experience:
- present the assistant's useful sentence as the primary content of each bubble
  rather than leading with internal action terminology
- keep action types available as subtle status or accessible metadata where they
  help the user understand a pending proposal or error
- show source cards only when reviewed guidance or a live lookup was actually
  used
- show an unavailable lookup once, without repeating substantially the same
  failure in both the assistant message and Tavily card
- after an explanation, offer contextual actions such as `Answer now`, `Explain
  more`, `Check official guidance`, and `Skip for now` when applicable
- keep proposals and confirmation controls visually distinct from ordinary
  conversation
- preserve the current PDF preview, progress display, manual field drawer, and
  shared confirmed-value state

Target conversation examples:

Example A — plain-language clarification without Tavily:

```text
Field: The date you began living at the address you ordinarily reside at
User: What does this mean?
Assistant: This is asking when you started living at your usual or main home
address. If you are unsure of the exact date, tell me what you remember and I
can help identify what is still missing without guessing it.
```

Expected behavior:
- Nemotron receives the bounded field context
- Tavily is not called
- no field value is proposed or changed
- the active field remains selected

Example B — uncertainty becomes a focused follow-up:

```text
User: I think it was around summer 2019.
Assistant: Do you remember the month, or only that it was during summer 2019?
I will not supply a more exact date than the one you know.
```

Expected behavior:
- the reply acknowledges the information already provided
- only the missing precision is requested
- no rejected or fabricated date is proposed
- the same field remains active in `awaiting_clarification`

Example C — a clear answer still becomes a proposal:

```text
User: I started living there on 12 June 2019.
Assistant: I understood the date as 12 June 2019. It is ready for your review
and has not been added to the form yet.
```

Expected behavior:
- the date adapter preserves the user's factual meaning and normalizes only to
  the format required by the field
- a typed proposal enters `awaiting_confirmation`
- the PDF is unchanged until explicit confirmation

Example D — external rule or requirement uses guidance:

```text
User: Is this legally required, and why do they ask for it?
Assistant: [Answer grounded in reviewed instructions or attributable live
guidance, or a concise statement that verified guidance is unavailable.]
```

Expected behavior:
- local reviewed guidance is preferred
- Tavily may run once when policy allows and local guidance is insufficient
- Nemotron cannot invent a purpose or requirement from the field wording
- any sources used are displayed separately and attributed

Example E — interruption and return to the form:

```text
User: What have we completed so far?
Assistant: You have confirmed 4 of 12 supported questions and skipped 1. We
were working on your move-in date. Would you like to answer it, explain it
again, or skip it for now?
```

Expected behavior:
- progress comes from deterministic field state
- the active field and conversation phase remain valid
- no model-proposed facts, Tavily lookup, or PDF update occurs

Examples of behavior to remove:
- returning `verified guidance is unavailable` for a harmless paraphrase of
  wording already present in the active field
- echoing the user's message or a `start`, `continue`, or `next` command as the
  assistant reply
- asking the identical question repeatedly without saying what part of the
  answer could not be used
- treating `yes`, `okay`, or `that makes sense` as confirmation of a pending
  factual proposal
- showing both a long assistant failure and a second Tavily card containing the
  same unavailable message
- invoking Tavily for ordinary field answers, navigation, progress summaries,
  or wording simplification

Acceptance criteria:
- genuine wording-clarification turns call Nemotron once and do not call Tavily
- Nemotron receives bounded active-field context, compact form context, progress
  state, and no raw PDF bytes
- a plain-language explanation directly paraphrases the available question
  before offering workflow choices
- wording explanations do not introduce a purpose, requirement, eligibility
  rule, legal conclusion, or personal field value that is absent from supplied
  context
- purpose, requirement, eligibility, official-instruction, and information-
  source questions remain on the reviewed-guidance and policy-gated Tavily path
- the backend, not the model, decides whether a live lookup occurs
- Tavily is not called for field answers, confirmations, navigation, progress
  summaries, uncertainty follow-ups, or simple paraphrasing
- uncertain or incomplete answers receive a specific follow-up that acknowledges
  usable information and identifies only the missing or ambiguous part
- the agent never converts uncertainty into a more precise factual proposal than
  the user supplied
- follow-up phrases such as `that`, `it`, `the previous question`, and `explain
  more simply` resolve against bounded active-field and recent-turn context
- explanations and progress questions preserve the active field and do not
  change confirmed values, skipped fields, or pending proposals
- after a non-mutating interruption, the assistant offers a natural return to
  answering, further explanation, official guidance, or skipping
- clear answers still produce type-compatible proposals that explicitly await
  confirmation
- proposal confirmation, edit-confirmation, rejection, skip, and automatic
  next-field progression retain their current deterministic state transitions
- a conversational acknowledgement can never count as confirmation
- progress summaries use canonical field state and report supported confirmed,
  unanswered, proposed, and skipped counts accurately
- the UI makes ordinary assistant messages primary and keeps proposals visually
  distinct
- source cards appear only when their corresponding reviewed or live guidance
  was actually used
- unavailable or empty guidance is communicated once with a concise recovery
  path and does not produce duplicated failure prose
- model, Tavily, and validation failures leave manual editing and the current PDF
  workflow usable
- deterministic transcript tests cover wording clarification, explanation
  follow-up, uncertain partial answers, correction, proposal, confirmation,
  progress summary, interruption, resume, skip, and evidence-dependent questions
- mocked tests assert model-call and Tavily-call counts for every routing class
- existing transcript fixtures retain a 100% completion rate, zero invalid
  actions, zero invalid proposals, zero confirmation-boundary failures, zero
  invented facts, and zero invented purposes
- an optional live Nemotron evaluation reports directness, contextual relevance,
  useful next-step rate, latency, and model calls for a small fixed conversation
  set without joining the default offline suite
- existing backend tests and frontend production build pass

Do not implement:
- voice input or output in this milestone
- a second model, model cascade, multi-agent debate, or agent framework
- autonomous model-selected tools or recursive web searches
- Tavily for ordinary conversation that can be answered by paraphrasing supplied
  form context
- invented personal facts, inferred purposes, legal advice, eligibility advice,
  or unsupported official requirements
- conversational confirmation of factual proposals
- unbounded history, server-side conversation persistence, authentication, or a
  database
- OCR, new PDF-format compatibility, direct PDF editing, or changes to PDF
  filling semantics

# Milestone 6.13.8 — Adaptive explanations and conversation repair

Status: COMPLETE

Live baseline recorded 11 October 2026 using
`nvidia/Nemotron-3_5-Lightning`:
- 5 fixed scenarios and 8 total model calls
- 100% valid-response and directness rates
- 80% contextual-relevance and useful-next-step rates
- 0% repeated-response rate
- 100% material-rephrasing and progressive-simplification rates
- 33.3% conversation-repair success rate
- 367 ms average model latency

The remaining failures were one follow-up that lost field context and one
continued-confusion response without a useful next step. These results are a
baseline for later evaluation; they do not authorize Milestone 6.14 by
themselves.

Problem to solve:
The assistant now routes ordinary wording questions to Nemotron with bounded
field and conversation context, but repeated requests such as `Explain that
more simply` can still receive the same answer with almost identical wording.
The response is structurally valid and safe, yet it does not recognise that the
previous explanation failed to help. This makes the assistant feel like a
repetitive form wizard rather than a patient conversational guide.

Goal:
Make wording explanations adapt across a conversation. Each follow-up should
respond to the user's demonstrated level of confusion, use materially different
language, and become progressively easier to understand without inventing form
purposes, requirements, personal facts, or answers. Keep the current single
Nemotron model, bounded history, deterministic state machine, and confirmation
boundary while producing evidence that can inform the later model-fallback
decision in Milestone 6.14.

Conversation-repair design:
1. The first wording request receives a short plain-language paraphrase of the
   active question.
2. A second request to simplify or explain again is classified as a
   conversation-repair turn, not another identical first-pass paraphrase.
3. The second explanation must use simpler and materially different wording
   from the previous assistant explanation.
4. If the user remains confused, the assistant may give one short, explicitly
   hypothetical example when an example can be generated safely from the
   supplied field meaning. The example must never be presented as the user's
   answer or as a value that should be entered.
5. If another safe rephrasing would not help, the assistant asks which word or
   part is unclear rather than repeating itself.
6. After any explanation, the active field and conversation phase remain valid
   and the user can answer, ask another question, request guidance, or skip.

Prompt and context design:
- define a restrained Formless persona in the trusted system prompt: calm,
  patient, plain-speaking, concise, and respectful of users who may be
  unfamiliar with official terminology
- keep safety and typed action rules authoritative; persona affects tone only
- preserve the existing maximum of eight recent user and assistant messages
  rather than adding unbounded or server-persisted history
- expose the previous explanation and deterministic explanation depth as
  explicit bounded context instead of expecting the model to infer them from a
  raw transcript alone
- add explicit turn objectives such as `initial_paraphrase`,
  `simplify_previous_explanation`, and `clarify_what_is_confusing`
- require repair responses to address the user's latest request directly and
  prohibit generic workflow commentary such as `this is the first unanswered
  field` unless the user asked about progress
- require a different sentence structure and simpler vocabulary when a previous
  explanation is supplied
- keep the active question, relevant help text, compact form context, progress,
  and bounded recent history; do not send raw PDF bytes

Deterministic safeguards:
- derive explanation depth and the previous explanation from bounded request
  history outside Nemotron
- detect exact and obvious near-duplicate explanations outside the model using
  a small deterministic comparison with no new dependency
- allow at most one correction attempt when a model response is structurally
  invalid or unacceptably repetitive, retaining the existing maximum of two
  model calls for a model-handled turn
- if the correction remains repetitive, return a concise deterministic prompt
  asking which term or part is unclear instead of exposing an error or looping
- an explanation, repair, or hypothetical example can never create a proposal,
  confirm a value, mutate field state, or update the PDF
- evidence-dependent questions remain on the reviewed-guidance and policy-gated
  Tavily path; conversational repair does not weaken grounding rules

Target conversation example:

```text
Field: The date you began living at the address you ordinarily reside at
User: What does this mean?
Assistant: It is asking when you moved into the home you normally live in.

User: Explain that more simply.
Assistant: When did you start living in your current home?

User: I still do not understand.
Assistant: For example, if someone moved into their current home on 5 March
2021, that would be their move-in date. You should use your own date. Is
`current home` or `move-in date` the part you would like me to explain?
```

Expected behavior:
- every assistant response remains attached to the same active field
- the second response is materially simpler and does not repeat the first
- the example is clearly hypothetical and cannot become a proposal
- the assistant does not infer why the organisation requests the date
- Tavily is not called
- the PDF and confirmed field values remain unchanged

Evaluation design:
- add deterministic transcript cases covering an initial explanation, repeated
  simplification request, safe hypothetical example, focused question about an
  unclear term, and return to answering the field
- add adversarial cases where a previous assistant message contains an invented
  fact, instruction, or proposed value and confirm that history remains
  untrusted data
- extend conversation-quality reporting with repeated-response rate, material-
  rephrasing rate, progressive-simplification rate, and conversation-repair
  success rate
- include the configured model name in optional live evaluation output so the
  same fixed scenarios can later compare the current Lightning model with a
  stronger Nemotron candidate
- keep live model evaluation optional and separate from the default offline test
  suite
- record latency and model-call counts so improved wording is not achieved by
  silently chaining multiple model calls on every turn

Acceptance criteria:
- the backend distinguishes an initial wording clarification from a repeated
  request to simplify or explain the same active field
- explanation depth and the previous assistant explanation are derived
  deterministically from no more than the existing eight-message history
- Nemotron receives a specific repair objective, bounded active-field and form
  context, progress state, and no raw PDF bytes
- the trusted system prompt defines the Formless conversational persona without
  weakening factual, guidance, proposal, or confirmation safeguards
- a repeated simplification request produces a materially different and simpler
  response rather than repeating the previous explanation
- explanations answer the wording question directly and omit unrelated progress
  or workflow commentary
- a hypothetical example is clearly labelled, remains generic, and cannot be
  parsed, proposed, confirmed, or written as the user's field value
- when the user remains confused, the assistant can ask which specific term or
  part needs explanation instead of entering a repetition loop
- exact or obvious near-duplicate model explanations receive at most one
  correction attempt, with no more than two total model calls for the turn
- repeated output after correction falls back to a useful deterministic
  clarification and never exposes a raw model-validation error
- explanations and repair turns preserve the active field, pending proposal,
  confirmed values, skipped fields, and PDF state
- Tavily is not called for initial paraphrasing, repeated simplification,
  hypothetical examples, or focused wording clarification
- questions about external purposes, requirements, eligibility, legal effect,
  official instructions, or information sources retain the existing grounded
  guidance routing
- deterministic tests cover explanation depth, bounded history, repetition
  detection, one correction attempt, safe fallback, state preservation, and the
  prohibition on proposals from explanation turns
- conversation-quality evaluation reports repeated-response, material-
  rephrasing, progressive-simplification, repair-success, latency, and model-
  call metrics for a fixed scenario set
- the optional live report identifies the configured model so results can inform
  Milestone 6.14 without changing or adding a model in this milestone
- existing transcript safety metrics remain at 100% completion with zero
  invalid actions, invalid proposals, confirmation-boundary failures, invented
  facts, and invented purposes
- existing backend tests and the frontend production build pass

Do not implement:
- a stronger or second model, model cascade, multi-agent workflow, or agent
  framework in this milestone
- multi-call prompt chains for every conversational turn
- higher temperature as a substitute for explicit conversation-repair policy
- unbounded history, server-side conversation persistence, authentication, or a
  database
- generic examples that could be mistaken for the user's factual answer
- invented form purposes, requirements, legal conclusions, eligibility advice,
  personal facts, or field values
- Tavily for explanations that can be produced from supplied field wording and
  bounded conversation context
- voice, OCR, new PDF compatibility, or changes to PDF filling semantics

# Milestone 6.13.9 — Conversational response contract and safe answer polishing

Status: COMPLETE

Verified implementation outcome:
- the public response contains `assistant_message`, one validated typed
  `effect`, canonical conversation state, and optional guidance metadata
- proposal effects preserve original and prepared values plus a concise
  transformation description
- the frontend presents conversation as the primary message and displays a
  separate proposal review card with Confirm, Edit, Use original when valid,
  Reject, and Skip controls
- deterministic preparation covers existing date, number, money, dropdown,
  and checkbox normalization plus reviewable name capitalization and
  presentation-only textarea polishing
- relevant confirmed answers enter bounded working memory only when the user
  explicitly refers to their field context
- offline transcript evaluation reports 90% prepared-value acceptance, 10%
  user edits, an 18.2% transformed-proposal rate, and 0% unsafe
  transformations while retaining zero invalid actions, invalid proposals,
  confirmation-boundary failures, invented facts, and invented purposes
- 275 backend tests and the frontend production build pass

Problem to solve:
The current Form Agent requires every turn to be represented as one workflow
action whose `message` also serves as the visible assistant reply. This protects
state transitions, but it couples natural conversation to commands such as
`explain`, `clarify`, `propose`, `skip`, and `next`. As a result, the assistant
can feel like a form wizard that happens to use chat bubbles instead of a
conversational partner that can optionally affect the form.

Clear user answers also receive uneven formatting. Dates, numbers, dropdowns,
and checkboxes already have useful deterministic canonicalization, while names,
addresses, postcodes, phone numbers, and prose mostly retain the submitted text.
The assistant should help prepare an answer for the form, but it must not
silently correct the spelling of a name, identifier, address, or factual
statement.

Goal:
Separate the assistant's conversational reply from the optional typed effect of
a turn, then add field-aware answer preparation that can show the user's
original answer beside a safely formatted or polished proposal. Nemotron should
provide a helpful conversational layer; deterministic backend code must remain
authoritative over routing, normalization policy, validation, conversation
state, confirmation, and PDF changes.

Target architecture:

```text
User message
    -> deterministic intent and state policy
    -> bounded conversational reasoning when needed
    -> optional candidate value from the user's own words
    -> field-type preparation and validation
    -> natural assistant message plus optional typed effect
    -> explicit user review and confirmation
    -> canonical field state and PDF preview update
```

Response-contract design:
- keep `POST /agent/respond` as the single public conversational endpoint
- replace the public assumption that the assistant message is itself the
  workflow action with a response envelope containing:
  - a primary `assistant_message` for natural conversation
  - one typed `effect` describing no form change, a pending proposal, confirmed
    value, rejection, skip, field selection, or completion
  - canonical `conversation_state`
  - existing reviewed-guidance and web-guidance metadata when actually used
- allow ordinary conversation to return a `none` effect without treating that
  as an error or inventing a field transition
- keep effects as a closed discriminated union validated by the backend; do not
  expose free-form model-selected tools
- keep proposals visually and semantically separate from the assistant message
- preserve deterministic confirmation, edit-confirmation, rejection, skip, and
  next-field transitions
- migrate the frontend and backend together; do not maintain two competing
  conversational endpoints

Bounded working context:
- preserve the recent eight-message transcript limit
- include a compact ordered form question map, the active field, nearby help
  and page context, current progress, and the latest explanation or proposal
- add deterministic structured working memory derived from canonical state,
  including active field, confirmed/skipped/proposed counts, and relevant prior
  confirmed answers when the user explicitly refers to them
- do not send every confirmed personal value on every turn when it is unrelated
  to the current request
- treat history, extracted form text, user answers, and prior assistant messages
  as untrusted model data
- never use a model-generated summary as the canonical source of the user's
  facts; canonical confirmed field state remains authoritative
- continue excluding raw PDF bytes from Nemotron prompts

Answer-preparation pipeline:
1. Preserve the exact user-supplied candidate as `original_value`.
2. Select a field-specific adapter from extracted field meaning and type.
3. Apply deterministic formatting when the conversion is unambiguous.
4. Use Nemotron only when conversational interpretation or prose polishing is
   genuinely needed.
5. Validate the prepared value against the field type, options, and field-
   specific rules.
6. Return a pending proposal containing the original and prepared values plus a
   concise description of any transformation.
7. Apply only the reviewed value after explicit confirmation.

Field-specific policy:
- dates: parse a clear natural-language date and format it exactly as requested
  by the field, such as `17 October 1986` to `17/10/1986`
- numbers and money: remove unambiguous presentation characters and preserve
  the user's numeric meaning; never turn an estimate or range into an exact
  number
- dropdowns and checkboxes: map only to one valid canonical option or boolean
- names: remove conversational framing and normalize harmless whitespace;
  capitalization may be suggested, but spelling and letter sequence are
  preserved unless the user explicitly requests a correction
- names with meaningful casing or particles, including `McDonald`, `O'Neill`,
  and `de la Cruz`, must not be damaged by naive title-casing
- addresses: preserve substantive tokens and spelling; permit only transparent
  whitespace or casing suggestions unless the user explicitly edits the value
- postcodes, phone numbers, email addresses, account numbers, passport numbers,
  and other identifiers: permit only validated format changes that do not
  change the underlying characters or digits
- short factual text: preserve the user's wording by default
- prose or explanation fields: Nemotron may offer spelling, punctuation, and
  grammar improvements, but must preserve names, dates, quantities, qualifiers,
  negation, uncertainty, and factual meaning
- no transformed value is described as corrected, saved, or added to the form
  before confirmation

Target conversation examples:

Example A — name capitalization remains a proposal:

```text
User: my name is john smith
Assistant: I understood the name as “john smith”. I have formatted the
capitalization as “John Smith”. Please check that the spelling and
capitalization are correct.
Effect: pending proposal
Original: john smith
Prepared: John Smith
```

Example B — requested date formatting:

```text
User: I was born on 17 October 1986
Assistant: Got it. The form requests DD/MM/YYYY, so I have prepared
“17/10/1986” for your review.
Effect: pending proposal
Original: 17 October 1986
Prepared: 17/10/1986
```

Example C — prose polishing without factual invention:

```text
User: i left because the hours was changed and i could not do nights
Assistant: I can tidy the grammar without changing your reason. Suggested
wording: “I left because the hours were changed and I could not work nights.”
Please review it, edit it, or use your original wording.
Effect: pending proposal
```

Example D — spelling is not guessed for identity data:

```text
User: jon smth
Assistant: I heard the name as “jon smth”. I will keep that spelling unless you
want to change it. Should I prepare it exactly that way?
Effect: no form change until the user resolves or confirms the spelling
```

Frontend experience:
- render `assistant_message` as the primary chat content without an internal
  action label leading the response
- render an effect card only when a turn has a meaningful form effect
- when formatting changed, show `You said` and `Prepared for the form` values
  together
- provide explicit `Confirm`, `Edit`, `Use original`, and `Reject` controls when
  applicable
- explain transformations concisely, such as `formatted as DD/MM/YYYY` or
  `capitalization suggested`; do not imply that AI output is authoritative
- preserve the existing PDF preview, manual field drawer, shared confirmed
  values, and preview-update behavior
- ordinary explanations, questions, and conversational acknowledgements must
  not display an empty proposal card or imply that the PDF changed

Evaluation design:
- add end-to-end transcripts that mix explanation, field answering, formatting,
  editing, confirmation, interruption, and automatic next-field progression
- test names with lowercase input, intentional uppercase, apostrophes, hyphens,
  particles, and non-English characters
- test date formats, money, numeric ranges, dropdown synonyms, checkbox answers,
  addresses, postcodes, phone numbers, emails, identifiers, and prose
- test that prose polishing preserves negation, uncertainty, names, dates,
  quantities, and the user's stated reason
- test that conversation-only turns always have a non-mutating effect
- report prepared-value acceptance rate, user-edit rate, unsafe-transformation
  rate, first-attempt proposal rate, turns per confirmed field, latency, and
  model calls per field
- retain the existing completion, invalid-action, invalid-proposal,
  confirmation-boundary, invented-fact, and invented-purpose metrics

Acceptance criteria:
- assistant conversation and typed form effects are separate properties in the
  backend response contract
- an ordinary conversational response can succeed with no form effect
- model wording cannot directly mutate conversation state, confirmed values, or
  the PDF
- every proposal identifies the field and exposes the exact prepared value
- when preparation changes visible text, the response preserves and returns the
  original candidate, prepared value, and transformation description
- deterministic adapters run before model-assisted interpretation or polishing
- dates are formatted according to unambiguous field instructions
- dropdown, checkbox, number, and money normalization retain their current safe
  behavior
- name capitalization suggestions preserve the supplied spelling and require
  confirmation
- identity values and identifiers never receive speculative spelling correction
- prose polishing preserves factual meaning, qualifiers, uncertainty, and
  negation and remains an explicitly reviewable proposal
- the user can confirm the prepared value, edit it, use the original value, or
  reject the proposal
- acknowledgement words such as `yes`, `okay`, or `that makes sense` cannot
  confirm a proposal outside the explicit confirmation event
- relevant confirmed answers can be included in bounded structured working
  memory when the user refers to them, without sending unrelated confirmed
  personal values on every turn
- confirmed, skipped, active, proposed, and completed field states retain
  deterministic transitions
- explanations, guidance questions, and general conversation cannot be parsed
  as personal field values merely because they mention an example
- the frontend keeps normal conversation visually separate from pending and
  confirmed form effects
- backend tests cover response-envelope validation, non-mutating conversation,
  each field-specific policy, transformations, edit/use-original/reject flows,
  and PDF-state boundaries
- transcript evaluation records preparation quality, user edits, unsafe
  transformations, latency, and model-call counts without requiring network
  access in the default suite
- existing PDF extraction and filling tests, Form Agent safety metrics, backend
  tests, and frontend production build pass

Do not implement:
- silent spelling correction or silent substantive rewriting of user answers
- automatic confirmation or direct model writes to canonical field state
- invented names, dates, addresses, amounts, reasons, explanations, or missing
  personal details
- using the assistant's hypothetical examples as candidate field values
- sending all personal answers to Nemotron on every turn without relevance
- a second model, model cascade, agent framework, or multi-agent review workflow
- unbounded history, server-side conversation persistence, authentication, or a
  database
- voice, OCR, new PDF-format compatibility, external form submission, or
  changes to low-level PDF filling semantics

# Milestone 6.13.10 — Natural conversation with deterministic effects

Status: COMPLETE

Audit baseline recorded 11 October 2026:
- 275 backend tests and the frontend production build pass
- the offline suite covers 5 curated transcripts, 36 turns, and 5 fixtures,
  with 90% first-attempt proposal acceptance, 3.8 turns per confirmed field,
  and zero invalid actions, invalid proposals, confirmation-boundary failures,
  invented facts, or invented purposes
- the offline completion metric describes selected evaluation fields, not every
  supported field in each real form
- a live run using `nvidia/Nemotron-3_5-Lightning` produced 100% valid, direct,
  and useful-next-step responses, 80% contextual relevance, 0% repeated
  responses, 66.7% repair success, 7 model calls, and 462 ms average latency
- the remaining live failure was a pronoun-based follow-up that lost the active
  field context

Problem to solve:
The assistant's state and safety boundaries are appropriately strict, but that
strictness has leaked into its language. Ordinary messages are routed through
too many narrow intents, objectives, canned fallbacks, and workflow phrases.
The result can be a form wizard presented in chat bubbles rather than a patient
assistant that listens, answers the user's actual message, and then continues
the form naturally.

The audit also found concrete demo gaps: older messages disappear from the
visible transcript, email and identifier answers can retain conversational
framing, typed input cannot naturally begin or continue after completion, live
follow-up context is imperfect, local provider configuration is easy to
misunderstand, and evaluation coverage can be overstated.

Goal:
Make the typed assistant feel like a coherent conversation while keeping every
form consequence deterministic and reviewable. Nemotron controls the wording
for model-handled ordinary dialogue; deterministic application wording remains
available for commands, safety fallbacks, and provider failures. Application
code controls state transitions, tool use, value validation, confirmation, and
PDF changes.

Core design rule:

```text
Flexible conversational message
              +
One closed, validated form effect
```

- `assistant_message` may acknowledge, explain, summarize, ask a useful
  follow-up, respond to a side question, or return naturally to the form
- `effect` remains a closed typed union and is the only part of the response
  that can influence conversation or form state
- a natural message cannot itself select, propose, confirm, skip, or write a
  field
- every effect is validated against the current phase, active field, supported
  options, field adapter, and canonical state before it is returned
- only an explicit confirmation event moves a proposal into confirmed state;
  only confirmed values can reach the PDF service

Conversational behavior:
- define the Formless persona and safety boundaries in the trusted prompt, but
  do not prescribe a fixed sentence structure, mandatory closing phrase, or
  button-like list of choices for ordinary responses
- let Nemotron phrase non-mutating conversation naturally from the user's latest
  message, active field, compact form map, canonical progress, and bounded recent
  history
- allow brief acknowledgements, follow-up questions, corrections, interruptions,
  and side questions without forcing every turn into `explain`, `clarify`,
  `next`, or another narrow conversational label
- preserve the user's terminology when helpful and adapt detail, vocabulary,
  and tone when the user asks again or appears confused
- answer the latest message before steering back to the active question; do not
  append the same workflow prompt to every response
- keep explanations concise by default, but allow additional detail when the
  conversation calls for it
- never invent a personal fact, form purpose, official requirement, legal
  conclusion, or field value in order to sound helpful

Routing without scripting the dialogue:
- handle unmistakable state-changing commands such as explicit confirmation,
  rejection, skip, and field selection deterministically
- run field adapters first for clear answers whose type and target are already
  unambiguous
- send ordinary or ambiguous conversational messages to Nemotron instead of
  relying on an expanding set of keyword templates
- allow Nemotron to interpret what the user is asking and to identify a
  candidate contained in the user's own words, but do not allow it to select a
  tool or make a state transition directly
- validate any candidate through the existing field-type preparation pipeline;
  an invalid or uncertain candidate becomes a natural clarification with no
  mutating effect
- keep Tavily eligibility and official-guidance selection under deterministic
  backend policy; simple wording help must not trigger web search
- use one model call for a normal model-handled turn and at most the existing
  single correction call for an invalid, unsafe, or context-losing response
- if model handling fails, return a grounded response that preserves the current
  field and keeps manual completion available rather than exposing a parser
  error

Context and transcript:
- retain the full visible transcript for the currently uploaded form in
  ephemeral frontend state while sending no more than the existing eight recent
  messages to the backend
- clear the transcript when the user deliberately loads another form; do not
  persist it to a server, database, or browser storage
- include the canonical active-field ID and question explicitly for relevant
  turns so `it`, `that`, and `this question` remain anchored correctly
- include a compact ordered question map and progress summary so Nemotron can
  understand the form without receiving raw PDF bytes or every personal answer
- typed input may begin the experience without clicking `Start`; a greeting or
  request for help starts the conversation but cannot become a field value
- after `form_complete`, allow read-only conversational summaries and questions
  about canonical progress without reopening or changing fields through free
  text

Answer preparation improvements:
- add focused deterministic adapters for email addresses and identifier-like
  fields, including passport, account, application, membership, reference, and
  document numbers
- remove only unambiguous conversational framing such as `my email is` while
  preserving the candidate's letters, digits, leading zeroes, casing, spaces,
  hyphens, and punctuation
- request clarification when multiple or partial candidates remain; never guess
  or externally verify a missing identifier character
- retain original and prepared values and require explicit review for every
  visible transformation
- keep automatic prose preparation presentation-only by default
- when the user explicitly requests help tidying a prose answer, Nemotron may
  offer one reviewable suggestion, but it must preserve names, dates, numbers,
  identifiers, quoted terms, negation, uncertainty, and stated reasons
- do not apply model rewriting to identity values, names, addresses, email
  addresses, phone numbers, or identifiers

Frontend and local demo behavior:
- render the assistant's message as normal conversation and show a separate
  effect card only when a meaningful effect exists
- keep proposal controls explicit without making every ordinary response end in
  the same menu of workflow choices
- keep the explicit `Start` button as an accessible alternative to typing
- document one exact backend launch path that exports `backend/.env` before
  starting FastAPI, without adding a general configuration framework
- keep `/health` as API availability only; do not imply that it proves Nemotron
  or Tavily is configured
- provider configuration failures must be specific and recoverable, must not
  expose credentials, and must leave manual PDF completion usable

Evaluation design:
- automated tests assert effects, state transitions, context bounds, safety,
  source routing, and value preparation; they must not require one exact natural-
  language sentence when multiple helpful responses are valid
- conversation-quality evaluation scores whether the response addresses the
  latest message, remains grounded in the active field, uses relevant recent
  context, avoids unnecessary repetition, and provides a useful next step
- add transcripts for natural start, interruptions, side questions, pronoun
  follow-ups, repeated explanations, email and identifier framing, ambiguous
  answers, explicit prose help, and post-completion summaries
- add longer multi-field sessions across the sample, household, I-9, SBA, and
  DS-11 fixtures using only supported and safely aligned fields
- report evaluated-field count, total supported-field count, field types, and
  fixture coverage so selected scenarios are not presented as full-form
  completion
- retain proposal-acceptance, user-edit, turns-per-field, repeated-question,
  clarification, invalid-action, invalid-proposal, confirmation-boundary,
  invention, unsafe-transformation, latency, and model-call metrics
- run the optional live suite with synthetic data and record the model name and
  results before deciding whether Milestone 6.14 is justified

Acceptance criteria:
- ordinary conversational turns can vary naturally in wording and structure
  while returning a valid non-mutating effect
- no prompt or response validator requires a canned opening, fixed closing, or
  repeated menu of actions for a normal assistant message
- deterministic code remains the sole authority over tools, phase changes,
  proposals, confirmations, skips, canonical values, and PDF updates
- ambiguous intent may receive model assistance, but model text cannot bypass
  typed-effect validation or explicit confirmation
- the assistant answers the user's latest message and remains connected to the
  correct active field across pronouns, interruptions, and repeated follow-ups
- a failed model response receives at most one correction attempt and then a
  useful grounded fallback without changing form state
- all current-form messages remain visible after more than eight chat messages,
  while backend requests contain no more than eight recent messages
- typed input can naturally start the conversation, and a pre-start greeting or
  help request cannot become a candidate field value
- completed conversations accept read-only progress and summary questions
  without mutating confirmed, skipped, proposed, or PDF state
- `my email is jane@example.com` prepares `jane@example.com`, and `my passport
  number is 00123-AB` prepares `00123-AB`, without changing their internal
  characters
- ambiguous email or identifier candidates produce a helpful clarification
  rather than an arbitrary proposal
- optional prose tidying remains user-invoked, reviewable, and preserves
  protected factual and uncertainty markers
- one documented local command sequence loads `backend/.env`; missing provider
  configuration has a clear recovery path and no credential is exposed
- evaluation reports its real field and fixture coverage and does not equate a
  curated scenario-completion rate with full-form completion
- the expanded deterministic suite retains zero invalid actions, invalid
  proposals, confirmation-boundary failures, invented facts, invented purposes,
  and unsafe transformations
- a recorded live run achieves at least 90% contextual relevance, at least 80%
  conversation-repair success, zero repeated responses, and zero safety-boundary
  failures; latency and model-call counts remain visible
- existing PDF extraction and filling tests, Form Agent tests, backend suite,
  and frontend production build pass

Verified implementation outcome recorded 11 October 2026:
- ordinary model-handled dialogue returns natural `conversation` or `explain`
  messages with a separately validated non-mutating effect; deterministic code
  remains the only authority for state, tools, proposals, confirmations, skips,
  canonical values, and PDF changes
- malformed, unsafe, repeated, or context-losing model output receives at most
  one correction call and then a field-grounded fallback without applying a
  value or exposing a parser error
- the frontend retains the full current-form transcript while requests remain
  bounded to the eight most recent messages; typed greetings can start the
  workflow and post-completion questions remain read-only
- email and identifier adapters remove only clear conversational framing and
  preserve internal characters; optional prose tidying is explicit,
  reviewable, and protected by deterministic factual-token checks
- the offline transcript evaluation covers 5 fixtures, 47 turns, and 18
  selected fields out of 324 supported fields across text, number, dropdown,
  and checkbox types; curated transcript completion is 100%, first-attempt
  proposal acceptance is 93.3%, invalid-action, invalid-proposal,
  confirmation-boundary, unsafe-transformation, invented-fact, and
  invented-purpose failures are all zero
- the recorded live synthetic run used `nvidia/Nemotron-3_5-Lightning` across
  9 scenarios and achieved 100% contextual relevance, 100% conversation-repair
  success, zero repeated responses, and zero safety-boundary failures; it made
  8 model calls (0.889 per scenario) with 398.882 ms average model latency
- all 288 backend tests pass and the frontend production build succeeds; the
  existing Vite bundle-size warning remains non-blocking

Do not implement:
- exact-string scripting of ordinary Nemotron responses
- letting free-form model text choose tools or mutate canonical state
- voice input or output
- a stronger or second model, model cascade, multi-agent workflow, or agent
  framework
- direct PDF field editing, widget highlighting, or the dedicated final review
  interface planned for Milestone 8
- unbounded model history, server-side transcript persistence, authentication,
  browser storage, or a database
- automatic confirmation, silent rewriting, speculative identifier correction,
  or external verification of personal information
- new Tavily routing, unrestricted search, OCR, XFA, scanned-form support, or new
  PDF filling semantics
- a new configuration framework, deployment infrastructure, Docker, or new
  application frameworks

# Milestone 6.14 — Controlled Nemotron model selection

Status: COMPLETE

Recorded live comparison outcome, 11 October 2026:
- primary: `nvidia/Nemotron-3_5-Lightning`
- candidate: `nvidia/Nemotron-3-Ultra-550b-a55b`
- both models ran sequentially through the same 9 fixed conversation-quality
  scenarios using the configured Nebius Token Factory account
- both achieved 100% valid responses, 100% directness, 100% contextual
  relevance, 0% repeated responses, and zero safety-boundary failures
- Lightning achieved an 88.9% useful-next-step rate and 66.7% conversation-
  repair success with 574.891 ms average model latency and 8 model calls
- Ultra achieved a 66.7% useful-next-step rate and 0% conversation-repair
  success with 2540.464 ms average model latency and 7 model calls
- Ultra regressed useful-next-step rate by 22.2 percentage points, regressed
  conversation-repair success by 66.7 percentage points, exceeded the 2500 ms
  average latency budget, and was 4.419 times slower than Lightning
- side-by-side review found Ultra's wording fluent and often concise, but it
  omitted a useful next step in all three repair scenarios and occasionally
  supplied more answer-format latitude than the bounded field context supported
- decision: keep `nvidia/Nemotron-3_5-Lightning` as the single primary model;
  do not add a runtime fallback or change the production default

Goal:
Compare the current fast Nemotron model with one stronger Nemotron candidate on
the same fixed Form Agent evaluation, then select one primary production model
from evidence. Prefer a direct primary-model replacement when it materially
improves the experience within the latency budget; do not add a runtime model
cascade merely because a larger model exists.

Evaluation design:
- the current `nvidia/Nemotron-3_5-Lightning` configuration remains the baseline
- the candidate must be an NVIDIA open model available through the configured
  Nebius Token Factory account
- both models receive the same system prompt, user prompt, bounded form context,
  recent history, state, sampling settings, token limit, and scenario order
- deterministic routing and field adapters run normally, so scenarios that do
  not require a model remain visible in the report but make no provider call
- the comparison reports each model's existing conversation-quality and safety
  metrics, average model latency, total calls, and per-scenario assistant output
- metric deltas and the latency ratio are calculated deterministically
- the automated recommendation requires no safety regression, no material
  quality regression, at least one material measured improvement, and an
  acceptable latency increase
- side-by-side response samples remain available for a final qualitative review
  of warmth, clarity, contextual understanding, and guided-interview usefulness
- the selected model remains configurable through `NEBIUS_MODEL`

Decision policy:
- select the candidate as the single primary model only when it materially
  improves the measured or reviewed conversation experience, retains zero
  safety-boundary failures, and remains responsive enough for the later voice
  interface
- keep Lightning when the candidate is worse, tied without a meaningful
  qualitative improvement, unavailable through Token Factory, or too slow
- record the compared model IDs, fixed scenario count, metrics, latency, model
  calls, representative response differences, and final decision
- changing the selected primary model must not change the Form Agent contract,
  deterministic routing, validation, explicit confirmation, or PDF boundaries

Acceptance criteria:
- one explicit command runs the same live conversation-quality scenarios against
  the configured primary model and one configured candidate model
- primary and candidate model identifiers remain server-side and no credential
  appears in evaluation output
- the live comparison runs the models sequentially rather than sending parallel
  duplicate requests
- the report includes both complete conversation-quality reports, per-scenario
  assistant messages, metric deltas, latency ratio, and an automated
  recommendation with deterministic reasons
- comparison logic treats safety-boundary failures as disqualifying
- comparison logic prevents a faster or more fluent candidate from winning when
  it regresses validity, contextual relevance, useful-next-step, repair, or
  repetition metrics beyond the documented tolerance
- comparison logic requires a material quality improvement rather than selecting
  a larger model solely because of its size or name
- the selected model is tested through the unchanged Nemotron Service, response
  parser, typed effect validation, confirmation boundary, and Form Agent API
- if the candidate wins, the default and example configuration are updated to
  that single model; if it does not, Lightning remains the default
- the final model-selection evidence and decision are recorded in this milestone
- normal automated tests use deterministic model doubles and make no network
  requests; the live comparison remains an explicit optional command
- existing backend tests, transcript evaluation, PDF tests, and frontend
  production build pass

Verified implementation outcome:
- `python -m evaluations.form_agent_model_selection` compares the configured
  `NEBIUS_MODEL` and `NEBIUS_CANDIDATE_MODEL` sequentially
- the report contains both metric sets, every scenario message, model-call and
  latency measurements, metric deltas, deterministic thresholds, reasons, and
  the recommendation
- candidate configuration stays server-side and no credential appears in the
  report
- deterministic tests cover material improvement, safety and quality
  regression, latency rejection, tied-result review, distinct configuration,
  and sequential execution
- the live recommendation was `keep_primary`, so the production default and
  runtime architecture remain unchanged

Do not implement:
- a runtime fallback model or automatic cascade in this milestone
- parallel calls to multiple models for an ordinary user turn
- model debate, model voting, multi-agent review, or an agent framework
- changing prompts, scenarios, thresholds, or sampling settings between models
  to favour one candidate
- selecting a model from parameter count or generic benchmarks alone
- weakening deterministic routing, validation, explicit confirmation, source
  grounding, or PDF separation to improve model scores
- automatic confirmation, voice, authentication, persistence, or a database

# Milestone 6.15 — Conversational navigation, correction, and review

Status: COMPLETE

Goal:
Let users move around the form, revisit skipped questions, safely correct
confirmed answers, and ask useful review questions through the typed
conversation before voice is added. Preserve the existing rule that natural
language can request an operation but only a closed, validated effect can
change canonical state.

Conversation and navigation behavior:
- the user may refer to an unanswered field by its question, label, section, or
  an unambiguous conversational description
- deterministic exact and normalized field-reference matching runs before
  Nemotron; model assistance may identify a candidate field only when the
  reference remains ambiguous
- every model-suggested field ID is validated against the supplied form schema,
  current field status, and allowed operation before it can become an effect
- selecting another unanswered field returns a closed field-selection effect
  and does not change any field value
- a skipped field can be explicitly reopened and becomes the active unanswered
  field without affecting confirmed values elsewhere
- ambiguous references produce a clarification listing only the smallest useful
  set of matching questions; the agent must not choose arbitrarily
- navigation acknowledgements ask the selected field's actual question and do
  not describe the navigation command itself as a form answer

Confirmed-value correction behavior:
- the user may request a correction to a confirmed field through conversation
- starting a correction keeps the existing confirmed value canonical and in the
  PDF preview while the replacement is discussed
- a replacement answer is returned as a reviewable proposal that identifies the
  field, previous confirmed value, user-supplied original candidate, prepared
  replacement value, and any visible transformation
- rejecting or abandoning the replacement preserves the previous confirmed
  value unchanged
- only an explicit confirmation event replaces the previous confirmed value;
  ordinary messages such as `yes`, `okay`, or `change it` cannot apply it
- confirmation replaces the value exactly once, updates the existing shared
  frontend state, and triggers the normal PDF preview flow exactly once
- corrections use the same field adapters, preparation rules, option checks,
  invention protections, and model-correction limit as first-time proposals

Conversational review behavior:
- while the form is in progress or complete, the user may ask which supported
  fields are confirmed, skipped, or unanswered
- the user may ask what confirmed value is currently stored for one
  unambiguously referenced field
- review answers are derived from canonical field state rather than conversation
  prose or model memory
- read-only review returns a non-mutating effect and cannot reopen, replace,
  confirm, skip, or fill a field
- post-completion review may navigate into an explicit reopen or correction flow
  only after the backend returns the corresponding validated effect; free-form
  text alone cannot leave `form_complete`
- summaries are bounded and use field questions or user-facing labels rather
  than exposing raw machine IDs unless needed to distinguish duplicate labels
- confirmed personal values are not sent wholesale to Nemotron; only the
  minimum value required for the user's specific review request may enter a
  bounded prompt, and deterministic responses are preferred when sufficient

State and effect design:
- extend the event, phase, pending-operation, and effect contracts only as much
  as required to distinguish navigation, reopening, first-time proposals, and
  replacement proposals
- the pending correction state retains both the previous confirmed value and
  the proposed replacement so frontend and backend can validate stale or
  duplicate events
- the frontend continues to treat the backend effect and resulting state as the
  authority; it must not infer a correction or navigation transition from the
  assistant's wording
- every effect is validated against a real stable field ID, the field's current
  status, the active operation, and the latest canonical value
- stale, duplicate, wrong-field, or phase-incompatible navigation and correction
  events fail safely without modifying frontend field state or PDF bytes
- the Form Agent continues to return messages and effects only; it never calls
  the PDF filling service or edits PDF bytes

Evaluation coverage:
- add complete multi-turn transcripts for selecting a later unanswered field,
  resolving an ambiguous field reference, reopening a skipped field, correcting
  a confirmed field, rejecting a correction, editing a correction before
  confirmation, and returning to review after form completion
- test that the previous confirmed value remains canonical after correction
  start, clarification, rejection, provider failure, invalid model output, and
  stale confirmation
- test that one explicit confirmation replaces the value once and advances
  deterministically without a duplicate PDF-preview update
- test specific post-completion questions and confirmed, skipped, and unanswered
  summaries without state mutation
- retain the existing invention, invalid-action, invalid-proposal,
  confirmation-boundary, repeated-question, latency, and model-call metrics
- normal backend tests use deterministic provider doubles; any optional live
  navigation evaluation remains separate and uses synthetic personal data

Acceptance criteria:
- an unambiguous conversational reference can select any unanswered supported
  field without changing its value
- an ambiguous reference asks for clarification instead of selecting a field
- a skipped field can be reopened explicitly and answered through the normal
  proposal flow
- a confirmed field can receive a replacement proposal while its previous value
  remains canonical and visible
- rejecting, cancelling, or failing a replacement proposal leaves the previous
  confirmed value unchanged
- explicit confirmation is required before a replacement reaches canonical
  state or the PDF preview
- confirmed replacement values update the shared state and PDF preview exactly
  once
- users can ask what value is stored for a specific confirmed field and receive
  a response grounded in canonical state
- users can list confirmed, skipped, and unanswered supported fields during and
  after completion without mutating state
- post-completion navigation and correction require closed validated effects;
  assistant wording cannot reopen or alter a field
- multi-turn transcript tests cover navigation, reopening, correction,
  rejection, edited confirmation, stale events, and post-completion review
- existing PDF extraction and filling behavior, proposal safety tests, backend
  suite, and frontend production build continue to pass

Verified implementation outcome:
- deterministic normalized matching selects unambiguous unanswered fields and
  returns a bounded clarification for ambiguous or missing references without a
  model call
- skipped fields reopen through a dedicated validated effect and then use the
  existing answer-adapter, proposal, and confirmation path
- confirmed-field corrections use distinct correction and replacement phases;
  the pending replacement retains the previous canonical value, original
  candidate, prepared value, and any visible transformation
- typed acknowledgements cannot confirm replacements; rejection, cancellation,
  model failure, and stale confirmation leave the previous confirmed value
  unchanged
- explicit confirmation or edited confirmation produces one existing
  `confirmed` effect, after which the frontend updates shared field state and
  the normal PDF preview flow once
- deterministic read-only review can list confirmed, skipped, and unanswered
  questions or return one specifically requested confirmed value during and
  after form completion
- the frontend validates every new phase, pending replacement, and effect
  against the request schema and canonical value before applying it, and shows
  the current value separately while a replacement awaits confirmation
- multi-turn backend coverage exercises navigation, ambiguity, reopening,
  correction, typed non-confirmation, rejection, cancellation, edited
  confirmation, stale events, model failure, and post-completion review
- all 305 backend tests and the frontend production build pass

Do not implement:
- voice input or output
- direct editing, highlighting, or navigation on the rendered PDF page
- the dedicated final-review interface planned for Milestone 8
- automatic confirmation or replacement of a confirmed value from free-form
  text alone
- fuzzy guessing between ambiguous fields
- sending every confirmed personal value to Nemotron for general context
- a second model, model cascade, multi-agent workflow, or agent framework
- new Tavily behavior, OCR, XFA, scanned-form support, or PDF filling semantics
- authentication, persistence, browser storage, a database, Docker, or
  deployment infrastructure

# Milestone 6.16 — Focused guided-interview UX

Status: COMPLETE

Design reference:
The local
[`Milestone 6.16 guided-interview reference`](docs/milestone-6.16-guided-interview-reference.md)
records the useful interaction pattern from the shared `Complete Form Together`
conversation. The requirements below are the authoritative scope; the
implementation must retain Formless's stronger proposal, confirmation,
grounding, and PDF-safety boundaries.

Problem to solve:
The typed Form Agent can converse, propose values, progress automatically, and
support navigation and correction, but the frontend still exposes those
capabilities as a general chat with workflow controls. A user completing a long
or unfamiliar form needs a calmer interview: one clearly framed question at a
time, a short acknowledgement of what just happened, controls appropriate to
the current field, and an obvious route to explanation, skipping, correction,
and review.

Goal:
Turn the existing typed conversation into a focused, one-question-at-a-time
form interview without creating a new agent path. Keep the PDF visible, make
the active question and current section easy to understand, collect answers
through conversation or field-appropriate controls, and preserve explicit
review before every AI-prepared value reaches canonical field state.

Target turn rhythm:
1. Show the current section, progress, and one active question.
2. Let the user answer naturally, use an appropriate quick control, ask for an
   explanation, or skip the question.
3. When an answer produces a proposal, show a compact review card containing
   the user's answer and the value prepared for the form.
4. Require an explicit confirm, edit, use-original, reject, or skip action.
5. After confirmation or skip, acknowledge the resolved field briefly and ask
   the next question in the same conversational flow.
6. When the form is complete, provide a concise conversational summary and
   routes to review or correct fields; leave the dedicated final-review
   workspace to Milestone 8.

Intended frontend experience:
- the PDF preview and guided interview remain the two primary workspace areas
- the interview emphasizes the active question rather than internal action,
  event, phase, or field-type terminology
- the active-question header shows available section, question or label, page
  number, and supported-field progress from existing extracted metadata
- only one active question is visually dominant at a time
- text and textarea fields use the normal conversational composer
- dropdown, radio, and checkbox fields may also expose compact quick-answer
  controls built only from validated schema options
- selecting a quick answer submits the same explicit Form Agent event as a
  typed answer and does not write directly to canonical state
- `Explain this`, `Skip for now`, and contextually valid correction or review
  actions remain easy to reach without appending a repetitive menu to every
  assistant message
- assistant acknowledgements are concise and specific, such as `Added your
  date of birth`, before the next real question is presented
- proposal review remains visually distinct from ordinary conversation and
  clearly states that the PDF has not changed yet
- when visible formatting changes, the card shows `You said` and `Prepared for
  the form` plus the existing transformation description
- after confirmation, the existing live PDF preview updates and the interview
  advances through the current deterministic progression path
- the full current-form transcript remains available without competing with
  the active question; older turns may be visually quieter or collapsible but
  must not be discarded
- loading, provider failure, validation failure, retry, and manual fallback are
  presented inside the interview context without clearing the active question
  or confirmed state
- the existing `Edit all fields` drawer remains the fallback and stays closed
  by default

Conversation and guidance behavior:
- the assistant asks the field's real grounded question and may add one short
  plain-language sentence when existing context safely supports it
- follow-up explanations answer the user's latest request before returning to
  the question; they do not repeat the same generic workflow instructions
- optionality, privacy warnings, requiredness, legal effect, and form purpose
  are shown only when supplied by verified form metadata or attributable
  guidance, never inferred merely to make the interview sound authoritative
- users may answer in their own words; deterministic adapters and Nemotron keep
  the existing interpretation and answer-preparation responsibilities
- unclear answers receive a focused clarification about the missing or
  ambiguous part while retaining the same active question
- the interview may offer schema-derived choices but must not reduce free-text
  conversation to a sequence of rigid buttons
- completion summaries and field-status answers come from canonical confirmed,
  skipped, proposed, and unanswered state rather than model memory

Architecture boundaries:
- continue using `POST /agent/respond` as the only Form Agent conversation
  endpoint
- reuse the existing `assistant_message`, typed `effect`, and canonical
  `conversation_state` contract; add contract fields only if implementation
  review proves existing extracted metadata cannot support the presentation
- keep one shared frontend field state for conversation, quick controls, the
  manual drawer, and PDF filling
- quick controls dispatch events through the same validated path and never
  mutate confirmed values directly
- Nemotron continues to control natural wording only for model-handled turns;
  deterministic code remains authoritative over tools, navigation, proposals,
  confirmation, skipping, canonical values, and PDF updates
- the Form Agent continues to return messages and typed effects and never
  calls the PDF Service
- the PDF Service and existing live-preview filling flow remain unchanged
- do not add a component framework or state-management library solely for this
  milestone

Representative experience:

```text
Personal details · Question 4 of 12
Assistant: What is your date of birth? Please use day, month, and year.

User: 17 October 1986

Assistant: I understood your date of birth and prepared it in the format this
form requests.

You said: 17 October 1986
Prepared for the form: 17/10/1986
Change made: formatted as DD/MM/YYYY
[Confirm] [Edit] [Use original] [Reject]

User confirms.

Assistant: Added your date of birth. Next, when did you begin living at your
current address?
```

Acceptance criteria:
- the interview presents one active supported question as the dominant task
- available section, page, and supported-field progress are shown from existing
  canonical or extracted metadata
- the assistant's conversational message is primary and internal action or
  phase names are not shown as chat content
- text answers can be entered naturally through the existing typed composer
- fields with validated finite options expose accessible quick-answer controls
  without preventing a typed response
- quick answers use the same Form Agent request, validation, proposal, and
  confirmation flow as typed answers
- answering through either input path cannot update a confirmed value or PDF
  before explicit confirmation
- every pending proposal identifies the active question and clearly says the
  value is awaiting review
- visible transformations show the original and prepared values plus the
  transformation description
- confirm, edit, use-original when valid, reject, and skip controls appear only
  when allowed by the current typed state
- confirmation and skip produce a concise acknowledgement and display the next
  unanswered question without requiring a separate Continue action
- explanation and clarification turns retain the current question and do not
  create empty proposal cards or duplicate generic action menus
- loading, retry, provider, and validation states preserve the active question,
  transcript, pending proposal, and confirmed field state
- the complete current-form transcript remains accessible even though the
  active question is visually emphasized
- manual controls remain available in the collapsed `Edit all fields` drawer
  and continue to share canonical state
- the PDF remains visible and confirmed answers continue to update its live
  preview through the existing filling flow
- reaching `form_complete` shows a concise canonical summary and offers review
  or correction through Milestone 6.15 behavior without introducing the
  dedicated Milestone 8 review workspace
- keyboard focus, control labels, and status announcements support the complete
  typed interview and explicit-confirmation flow
- frontend production build and existing backend, PDF, Form Agent, safety, and
  transcript tests pass

Verified implementation outcome:
- the assistant workspace now presents one dominant active-question card with
  grounded section, page, real question text, and supported-field position,
  while the existing canonical progress summary remains visible above it
- validated dropdown options and checkbox states appear as accessible compact
  quick answers; every quick answer calls the same `message` event path as the
  typed composer and cannot update canonical state or the PDF directly
- explanation, live-guidance, and stale-safe skip actions are centralized on
  the active question instead of being repeated under every assistant message
- assistant messages no longer expose internal effect or phase labels, and the
  complete current-form transcript can switch between the three most recent
  messages and the full retained conversation without discarding history
- proposal review identifies the active question, says explicitly that the PDF
  is unchanged, preserves original/prepared/transformation details, and shows
  only the confirmation, edit, use-original, reject, skip, or correction
  controls allowed by the current typed state
- normal confirmation and skip responses continue through the backend's
  deterministic next-question transition without a separate Continue action;
  a distinct Resume action remains only for the existing direct/manual-edit
  compatibility phases
- form completion is a compact canonical confirmed/skipped/unanswered summary
  with conversational review and correction routes provided by Milestone 6.15
- loading, retry, validation, and provider states remain inside the interview
  without clearing the active question, proposal, transcript, or confirmed
  values; the collapsed manual drawer and live PDF filling flow are unchanged
- focus returns to the typed composer when an answer or clarification is
  expected, and the new quick, transcript, completion, and review controls have
  explicit labels, focus styling, and live status context
- the focused desktop layout was rendered in the local browser with no console
  errors, the sample fixture exposed the expected section/page/finite-choice
  metadata, all 305 backend tests pass, and the frontend production build passes

Do not implement:
- voice input, speech recognition, or speech output
- automatic confirmation, conversational confirmation, or silent PDF updates
- a second conversation endpoint, voice-specific agent, second model, model
  cascade, multi-agent workflow, or agent framework
- direct editing, field overlays, highlighting, or automatic page navigation
  on the rendered PDF
- the dedicated final-review workspace, PDF field clicking, or geometry work
  planned for Milestone 8
- invented optionality, privacy claims, form purposes, requirements, legal or
  eligibility guidance, personal facts, or field values
- changes to PDF extraction or filling semantics
- OCR, XFA, scanned-form support, online forms, or new PDF compatibility
- unbounded backend history, server persistence, browser storage,
  authentication, a database, Docker, or deployment infrastructure

# Milestone 7 — Voice

Status: COMPLETE

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

Verified implementation outcome:
- the guided interview exposes an explicit `Start voice answer` control and
  clear permission, listening, processing, editable-review, error, and retry
  states; it never records continuously or starts without a user action
- browser-recognized speech remains a local draft until the user stops capture,
  reviews and edits the visible transcript, and selects `Send transcript`
- sending a reviewed transcript calls the existing `sendAgentMessage` path,
  so voice uses the same `POST /agent/respond`, typed effects, proposal review,
  explicit confirmation, canonical field state, and PDF filling flow as typing
- cancel aborts the active recognition session, clears its draft, and sends no
  agent event or field update; stale recognition callbacks are session-guarded
  so they cannot restore or submit a cancelled transcript
- spoken replies are deliberately opt-in, read the same already-visible
  `assistant_message`, can be stopped, stop automatically when listening begins,
  and fall back to the persistent text response if speech output fails
- denied permission, missing microphone, no speech, unavailable recognition
  service, unsupported language, insecure/unsupported browser input, and speech
  output failure each have bounded recovery text while the typed composer stays
  available
- changing PDFs aborts active recognition and speech without persisting audio,
  transcripts, or voice settings outside the current browser session
- a local browser interaction harness exercised start, listening, stop,
  editable transcript correction, submission, cancellation without submission,
  permission denial, retry, unsupported-input fallback, opt-in speech output,
  and visible stop-speaking controls without using real personal audio
- all 305 backend tests pass, the frontend production build passes, and no new
  endpoint, model, agent, persistence layer, or frontend dependency was added

Do not implement:
- always-on recording or wake-word detection
- voice-controlled confirmation without a visible confirmation state
- a separate voice agent or duplicate form state
- authentication, persistence, or a database

# Milestone 7.1 — Human-helper voice interview

Status: COMPLETE

Problem to solve:
Milestone 7 added safe speech input and output, but the user still has to start
each recording, stop it, review it, send it, and separately decide when the
assistant should speak. That is useful dictation, not the intended experience
of a patient helper sitting beside the user, asking one question at a time,
listening, checking what should be entered, and moving through the form.

Goal:
Turn the existing speech adapter into an explicit, turn-based voice interview
around the same typed Form Agent. Once the user starts a voice conversation,
the assistant speaks the visible question or response, listens for one user
turn, sends the visible transcript through the existing message path, and
continues from the backend's validated state and effect. The PDF changes only
after an explicit confirmation event.

Target voice rhythm:
1. The user selects `Start conversation`; no microphone starts before this
   deliberate action.
2. The assistant speaks the same question or response shown in the interview.
3. When speech finishes, the interface clearly enters one listening turn.
4. The user answers naturally; the recognized transcript remains visible and
   can be corrected, while the completed utterance is sent through the same
   Form Agent message event as typed text.
5. If the answer becomes a proposal, the visible proposal card remains the
   source of truth and the assistant asks for confirmation aloud.
6. A bounded confirmation phrase such as `confirm that` or `put that in` maps
   to the existing explicit confirmation event only while that proposal card is
   visible. The same words cannot confirm anything in another state.
7. Rejection, correction, skip, explanation, pause, and ordinary answers remain
   available by voice without creating a second form-state path.
8. After confirmation or skip, the backend's existing acknowledgement and next
   question are spoken, then the next listening turn begins.

Voice-session design:
- add a small frontend voice-session orchestrator with explicit states for
  inactive, starting, assistant speaking, listening, preparing a transcript,
  waiting for the Form Agent, awaiting confirmation, paused, complete, and
  recoverable error
- use turn-based capture rather than always-on recording; every recognition
  session ends after one utterance or when the user stops it
- keep microphone, speech-recognition, and speech-synthesis mechanics inside
  the existing browser voice adapter
- keep recognition transcripts visible during processing and proposal review;
  typed input and the existing review buttons remain available at all times
- allow the user to interrupt spoken output and answer immediately; starting a
  listening turn stops current speech first
- provide visible `Pause`, `Resume`, and `End conversation` controls that stop
  microphone capture and speech without changing form state
- if speech input or output is unavailable, denied, or fails, preserve the
  current question, proposal, transcript, typed composer, and manual fallback
- read back the backend's prepared-answer wording before accepting spoken
  confirmation; never construct a separate voice-only proposal

Closed voice-command policy:
- outside a visible pending proposal, recognized speech is an ordinary Form
  Agent message except for local pause/end commands and a field-scoped skip
- while a proposal is visibly pending, only a small exact set of affirmative
  phrases can dispatch the existing explicit `confirm` event
- exact rejection and skip phrases dispatch their existing validated events
- a spoken correction such as `No, I said 17 October 1987` first rejects the
  pending proposal, then submits only the user-stated replacement through the
  normal answer path; the replacement still requires a fresh explicit
  confirmation
- unrecognized or ambiguous confirmation language remains an ordinary message
  and cannot mutate canonical field state
- voice parsing never writes a value directly, calls the PDF service, chooses a
  field value, or treats assistant speech as user input

Architecture boundaries:
- continue using `POST /agent/respond` as the only conversational endpoint
- keep the existing `assistant_message`, typed `effect`, and canonical
  `conversation_state` as the authority for every turn
- keep one shared frontend field state for voice, typed conversation, quick
  answers, manual editing, and PDF filling
- keep speech recognition and synthesis entirely in the frontend; do not send
  audio to FastAPI, Nemotron, Nebius, or Tavily
- keep Nemotron and deterministic Form Agent routing unchanged
- do not add a frontend state library, voice SDK, second model, second agent, or
  voice-specific backend endpoint

Acceptance criteria:
- one explicit `Start conversation` action starts a turn-based voice session
- the assistant speaks the same response that remains visible in the transcript
- listening begins only during an active voice session and only for one user
  turn at a time
- the UI clearly distinguishes assistant speaking, listening, transcript
  preparation, waiting for the agent, awaiting confirmation, paused, complete,
  unsupported, and error states
- a completed spoken answer is visibly transcribed and uses the same Form Agent
  message event, endpoint, validation, proposal, and confirmation flow as typing
- speech recognition never writes directly to confirmed field state or the PDF
- a bounded spoken confirmation becomes the existing explicit confirmation
  event only while the matching proposal card is visibly pending
- the same confirmation phrase outside a pending proposal cannot confirm or
  update any field
- spoken rejection and skip use the existing closed validated events
- a spoken correction rejects the old proposal, submits a new candidate through
  the normal answer path, and still requires explicit confirmation before a PDF
  update
- after confirmation or skip, the assistant speaks the deterministic
  acknowledgement and next real question without a separate Continue action
- the user can interrupt assistant speech to answer, pause or end the voice
  session, and resume without losing conversation or field state
- pausing, ending, cancelling, permission denial, no-speech, recognition error,
  and speech-output failure do not change confirmed values or PDF bytes
- the recognized transcript remains visible and correctable; typed input and
  visible proposal controls remain permanent fallbacks
- changing PDFs terminates the active voice session and clears its transient
  transcript without persistence
- frontend production build and existing backend, PDF, Form Agent, safety, and
  transcript tests pass

Verified implementation outcome:
- one `Start conversation` control begins a frontend-only session that speaks
  the current visible assistant turn, opens one one-shot recognition turn after
  speech ends, submits the completed transcript through the existing Form Agent
  message path, and continues from the returned typed effect and state
- the voice UI distinguishes inactive, starting, assistant-speaking,
  microphone-permission, listening, transcript-processing, agent-processing,
  pending-confirmation, paused, complete, unsupported, and recoverable-error
  conditions while keeping the typed composer and visible proposal controls
- exact confirmation, rejection, and skip phrases become their existing closed
  events only in compatible state; `yes` outside a pending proposal remains an
  ordinary message and cannot confirm or update a field
- a spoken correction rejects the current proposal, queues only the replacement
  stated by the user, submits it through the normal answer path, and requires a
  fresh explicit confirmation before canonical state changes
- pausing, ending, cancelling, interrupting speech, microphone failure, and
  changing forms stop transient browser speech work without applying a value;
  stale recognition and speech callbacks remain session-guarded
- the latest transcript stays visible through agent processing and spoken
  proposal review, can be edited and resubmitted, and is replaced only when the
  next listening turn produces new recognized speech
- a local browser harness using synthetic, non-personal speech exercised start,
  answer, proposal, spoken correction, replacement proposal, explicit spoken
  confirmation, deterministic next-question progression, spoken pause, and the
  out-of-context `yes` boundary; the temporary harness was removed afterward
- all 305 backend tests pass, the deterministic 5-fixture/47-turn transcript
  evaluation reports no failures or safety-boundary regressions, and the
  frontend production build passes with only the existing PDF-worker chunk-size
  warning

Do not implement:
- always-on recording, background listening, wake-word detection, or recording
  before the user starts the session
- automatic acceptance of a proposed factual value
- confirmation from fuzzy sentiment, assistant wording, or a voice phrase when
  no matching proposal is visibly pending
- direct voice-to-PDF writes, audio upload, audio storage, or transcript
  persistence
- a separate voice agent, second conversational endpoint, model cascade,
  multi-agent workflow, or agent framework
- direct PDF field interaction, final-review workspace, or other Milestone 8
  work
- authentication, browser storage, a database, Docker, deployment, OCR, XFA,
  scanned-form support, or online forms

# Milestone 7.2 — Automated conversation evaluation baseline

Status: COMPLETE

Problem to solve:
The existing test suite proves individual routing, validation, safety, and
state-machine behaviors, and its curated transcript evaluator proves several
known complete paths. It does not reproduce the messier ways people actually
talk while completing a form, retain every request/response/state transition
as an artifact, score deterministic form correctness together with qualitative
conversation quality, or compare the same suite between code/model versions.
Without that baseline, changing prompts or interpretation logic risks improving
one demo transcript while silently regressing accuracy, confirmation safety, or
another conversational behavior.

Goal:
Add a test-only conversation evaluation lab that drives the existing Form Agent
application boundary over real schemas extracted from the supported PDF
fixtures. Fixed synthetic personas and conversations must exercise bundled
answers, corrections, ambiguity, questions, interruptions, skipping,
frustration, and revisiting. Every run must save complete evidence and support a
like-for-like comparison before any production conversation changes are made.

Evaluation architecture:
- keep all simulator, scenario, scoring, judge, report, and comparison code
  under `backend/evaluations`; do not put evaluation policy in the Form Agent
- load supported `FormAgentField` schemas through the existing PDF extraction
  service from checked-in PDF fixtures
- drive either the public in-process `FormAgentService.respond` boundary or a
  running API's existing `POST /agent/respond` endpoint
- mirror the frontend's typed effects when constructing the next request, so
  only confirmed and skipped effects change the simulator's canonical field
  state
- use fixed, versioned, synthetic scenarios rather than model-generated user
  turns, keeping before/after comparisons repeatable and free of personal data
- treat exact field state, phase/effect expectations, safe proposal grounding,
  context checks, repetition, and recovery as deterministic evidence
- optionally use configured Nemotron as an evaluation-only qualitative judge
  for naturalness, context awareness, clarification quality, recovery, and
  possible invention; qualitative scores never override form-state failures
- write JSON containing every turn, expected result, actual form state, scores,
  latency, and failure reasons, plus a human-readable Markdown transcript
- attach the scenario-suite digest, target/model, Git revision, label, and time
  to every run, and compare only reports produced from the same suite digest
- ignore generated result files in Git while keeping the scenario definitions,
  harness, tests, command, and checked baseline summary versioned

Required scenario coverage:
- a user supplies multiple fields in one message and expects volunteered data
  to remain available
- a user corrects a confirmed value while another confirmed value is preserved
- an incomplete answer triggers one useful clarification rather than a guess
- a user asks what a field means and asks a contextual follow-up
- a user interrupts the active question, checks progress, and resumes
- a user skips a field and later reopens it
- a confused or frustrated user asks for simpler wording
- a user returns to an earlier confirmed question and resumes the prior task

Metrics:
- conversational naturalness, both a transparent bounded heuristic and an
  optional qualitative judge score
- context-retention rate over explicitly tagged turns
- expected canonical form-state accuracy
- unnecessary adjacent-response repetition rate
- clarification quality for tagged ambiguity/explanation turns
- recovery success for correction and misunderstanding scenarios
- ungrounded proposal or unsupported-claim failures
- completed-turn rate and average Form Agent response latency
- deterministic and qualitative failure counts with per-scenario reasons

Acceptance criteria:
- the suite includes distinct realistic personas and all required scenarios,
  using synthetic personal information only
- every scenario uses fields extracted from an existing PDF fixture rather than
  a duplicate hand-written production schema
- the simulator calls the existing Form Agent service boundary and offers an
  HTTP mode for the existing endpoint
- every turn records the user event, visible message, request state, fields
  before and after, assistant response, typed effect, resulting state, latency,
  expectation failures, and provider/API errors
- deterministic scoring covers form accuracy, context, repetition,
  clarification, recovery, and whether proposed information is user-grounded
- optional qualitative scoring produces bounded naturalness, context,
  clarification, recovery, invention, summary, and failure-reason fields
- a run saves full JSON and Markdown artifacts without logging credentials
- a compare command rejects unlike suite digests and reports metric deltas plus
  stable fixed, new, and unchanged deterministic failures
- normal tests use deterministic services and make no provider requests
- no production Form Agent, PDF, frontend, or voice behavior changes while the
  baseline is being established

Verified implementation outcome:
- eight synthetic personas drive eight complete scenario definitions containing
  47 scheduled turns over the sample, household-support, and USCIS I-9 PDF
  fixtures
- the simulator can call `FormAgentService.respond` in process or
  `POST /agent/respond` over HTTP, applies only validated typed effects to its
  local canonical fields, and retains partial transcripts when a transition or
  provider call fails
- generated JSON and Markdown reports contain expected/actual state, full
  transcripts, deterministic scores, optional Nemotron rubric results, failure
  reasons, target/model identity, suite digest, Git revision, and latency
- `python -m evaluations.conversation_harness compare` successfully compared
  two reports with the same suite digest and reported metric deltas
- the final live Nemotron baseline completed 42 of 47 scheduled user turns
  (`0.894` completed-turn rate), achieved `0.500` exact form-state accuracy,
  `0.619` context retention, `0.333` recovery success, `0.062` unnecessary
  repetition, `4.667/5` heuristic clarification quality, `4.938/5` heuristic
  naturalness, and zero deterministic invented-value failures
- all eight qualitative assessments completed after one bounded invalid-rubric
  retry; the judge reported `3.875/5` naturalness, `3.625/5` context awareness,
  `3.833/5` clarification quality, and `3.600/5` recovery quality
- focused harness tests pass without network access and the unchanged existing
  backend, transcript, safety, PDF, and frontend checks remain required

Baseline weaknesses to address next:
- bundled answers are treated as ambiguous and the volunteered later-field
  value is not recoverable on the next question
- common conversational wrappers such as `Please call me Alex` and `Okay, my
  first name is Jordan` are stored wholesale instead of extracting the intended
  field value
- complete spoken month-name dates such as `the sixth of March 1992` and `I
  moved in on 2 September 2021` are rejected rather than safely normalized
- progress responses retain counts and the active field but do not identify the
  confirmed answer the user asked about
- `go back to the full name question` does not start the already-supported
  closed correction flow, so the following cancellation is interpreted against
  the wrong field
- prose can sound warm and helpful while the strict interpretation layer still
  blocks accurate completion; deterministic state accuracy must therefore stay
  authoritative over qualitative fluency scores

Do not implement:
- production prompt, policy, adapter, state-machine, PDF, frontend, or voice
  changes in this baseline milestone
- generated or real personal information
- an autonomous user model whose changing output prevents version comparison
- a second production agent, runtime model cascade, agent framework, database,
  analytics service, or transcript persistence
- Milestone 7.3 reliability changes or Milestone 8 workflow changes

# Milestone 7.3 — Evidence-gated conversational reliability pass

Status: COMPLETE

Goal:
Make the smallest production changes that directly address the Milestone 7.2
baseline failures, then rerun the exact same suite and accept changes only when
the comparison improves form accuracy and recovery without an invention or
confirmation-boundary regression.

Planned targeted changes:
- add field-aware extraction of common answer wrappers for names and short text
  while preserving the user's actual spelling and factual content
- accept and conservatively normalize unambiguous spoken month-name dates for
  fields whose schema requests a date
- handle a bundled active-field answer without treating the unrelated supplied
  detail as part of that value, and use bounded history when the user says they
  already supplied the next answer
- expand deterministic conversational navigation for natural `go back to`
  references to a confirmed question, retaining the old value until explicit
  replacement confirmation
- make progress/review answers identify relevant canonical fields and values
  when the user asks, without exposing or inventing unrelated information
- keep explanatory examples and format advice bounded by extracted schema or
  verified form context
- add unit and transcript tests for every accepted interpretation before
  changing the baseline comparison result
- rerun Milestone 7.2 with the same suite digest, save a candidate report, and
  use the compare command to demonstrate fixed failures and any regressions

Acceptance criteria:
- bundled-answer, conversational-wrapper, natural-date, interruption, skip,
  frustration, correction, and return-to-earlier scenarios all complete or
  fail with an actionable clarification rather than an invalid transition
- exact form-state accuracy and recovery success materially improve from the
  recorded baseline
- context retention does not regress
- invented-information failures and confirmation-boundary failures remain zero
- replacement corrections preserve the current confirmed value until explicit
  confirmation
- the same fixed scenarios and suite digest are used for baseline and candidate
  reports
- all backend, PDF, Form Agent, safety, transcript, harness, and frontend checks
  pass

Verified implementation outcome recorded 13 October 2026:
- the unchanged `guided-interview-baseline-v1` suite and digest
  `c5d8e5503835468a` were used for both the recorded baseline and candidate
- all 47 scheduled turns completed, up from 42; no scenario stopped on an
  invalid transition
- exact form-state accuracy improved from `0.500` to `0.875`, recovery success
  from `0.333` to `0.857`, and context retention from `0.619` to `1.000`
- unnecessary repetition fell from `0.062` to zero and deterministic failures
  fell from 34 to 3
- deterministic invention failures, single-turn invented facts and purposes,
  transcript confirmation-boundary failures, invalid actions, invalid
  proposals, and unsafe transformations all remained zero
- the existing confirmed value remained canonical throughout replacement
  correction and cancellation scenarios
- the only remaining suite mismatch is presentation-only: for an occupancy-date
  field whose extracted schema specifies no format, the assistant safely keeps
  the unambiguous user wording `2 September 2021` instead of silently changing
  it to the scenario's expected `02/09/2021`
- 323 backend tests pass, the 47-turn curated transcript evaluation has no
  failures, the 14-scenario safety evaluation has no failures, and the frontend
  production build succeeds with only the existing bundle-size warning

Do not implement:
- broad Form Agent rewrites or a new conversation architecture
- a second production agent, agent debate, or runtime model cascade
- voice changes, direct PDF interaction, final-review UI, or Milestone 8 work
- authentication, persistence, a database, deployment, OCR, XFA, or online forms

# Milestone 7.4 — Voice-like conversation reliability benchmark and repair

Status: COMPLETE

Problem to solve:
The first real turn-based voice interview showed that speech capture is usable,
but semantic handling and response presentation can still feel like a rigid
form validator. In particular, the assistant may ignore the newest short
answer in favour of an older transcript value, reject a safe near-match for a
finite option, repeat formal validation text, claim a date format that is not
present in the extracted schema, or confirm an edited value without making the
edit visible in the conversation. These failures must be made reproducible
before production behavior changes again.

Goal:
Extend the existing test-only conversation harness with a fixed synthetic
regression suite modelled on the observed voice interview, record the current
baseline, make only bounded interpretation and response-policy improvements,
then rerun the identical suite. Improve the sense that a patient helper heard
the user's latest answer while preserving closed effects, explicit
confirmation, exact form state, and the no-invention boundary.

Evaluation-harness scope:
- add per-turn positive and negative message assertions so a scenario can
  require acknowledgement of the current answer and reject stale or
  contradictory wording
- add explicit tags and aggregate metrics for latest-answer adherence and
  assistant contradictions instead of hiding those failures inside the broad
  context-retention score
- make the qualitative naturalness rubric explicitly penalize templated status
  narration, failure to answer the latest utterance, and contradictions with
  the visible transcript or canonical state
- add a separate fixed synthetic suite covering an unsupported format claim,
  a voice-like dropdown near-match, `nobody` followed by the newer answer
  `one`, and an edited confirmation whose changed value must be visible
- save baseline, candidate, comparison, full transcript, expected result,
  actual state, metrics, and failure reasons using the existing ignored results
  directory and compare only the same suite digest
- keep the completed Milestone 7.2 baseline suite unchanged and rerun it as a
  regression check after the targeted changes

Targeted production scope:
- treat an unambiguous spoken whole-number word as the current numeric answer,
  with the newest user message authoritative for that turn
- when a count question explicitly says to include the user, interpret
  `nobody` or `no one` as ambiguous and ask whether the user means nobody else,
  rather than proposing zero or letting old transcript text override the next
  answer
- accept only a unique, high-confidence finite-option near-match; ambiguous or
  materially different dropdown wording must still receive clarification
- validate model explanations against the active field metadata so the
  assistant cannot present an absent date format as a requirement
- make deterministic proposal, clarification, and edited-confirmation wording
  shorter and more conversational while retaining an explicit review boundary
  and never implying that an unconfirmed value reached the PDF
- strengthen the model prompt to treat the latest user message as the current
  turn's source and bounded history only as context

Representative repaired exchange:

```text
Assistant: How many people normally live with you and share food or essential
costs? Include yourself.

User: Nobody.

Assistant: Do you mean nobody else? This question says to count yourself, so
if it is just you the number would be 1. Tell me the exact count to use.

User: One.

Assistant: I heard 1. Please check it before I add it to the form.
```

Acceptance criteria:
- the new fixed suite uses only synthetic information and real extracted fields
  from checked-in PDF fixtures
- every regression turn records the same complete evidence as the existing
  harness and can run through the in-process service or existing HTTP endpoint
- per-turn assertions can require all expected terms and reject forbidden terms
- reports expose latest-answer adherence and contradiction counts, and the
  compare command reports their direction and deltas
- a current baseline is saved before targeted production changes and a
  candidate is run against the identical suite digest afterward
- `one` deterministically proposes `1` for the observed count field even after
  an earlier `nobody` clarification, without repeating or proposing the stale
  answer
- `nobody` on a count-yourself question produces a focused clarification and
  no proposal or canonical field change
- `solo tenant` may prepare the single safe `Sole tenant` option for explicit
  review, while unrelated or ambiguous wording is not guessed
- an explanation cannot claim `DD/MM/YYYY`, `MM/DD/YYYY`, or another required
  date format unless that format is present in active field metadata or
  supplied verified guidance
- edited confirmation wording explicitly tells the user that their reviewed
  edit, rather than the earlier proposal, was applied
- deterministic messages are concise, refer to the current answer or question,
  and retain explicit confirmation before any canonical value changes
- exact canonical form-state accuracy does not regress; proposal/action
  accuracy and latest-answer adherence improve on the targeted baseline;
  contradiction failures decrease; invention and confirmation-boundary
  failures remain zero
- the unchanged Milestone 7.2 suite does not regress on exact form-state
  accuracy, context retention, recovery, invention, or confirmation safety
- focused harness and Form Agent tests, the complete backend suite, curated
  transcript and safety evaluations, and frontend production build pass

Verified implementation outcome recorded 14 October 2026:
- a separate four-persona, four-scenario synthetic suite now exercises real
  extracted household-support fields for unsupported date advice, a safe
  dropdown near-match, `nobody` followed by `one`, and edited confirmation
- per-turn expectations can require every relevant phrase, reject stale or
  contradictory phrases, and bound response length; reports now expose
  latest-answer adherence and contradiction failures, while suites without
  those tagged turns report the metric as not scored
- the pre-change and final live reports use the identical suite digest
  `d8aac2d7708deb62`; all 12 turns completed in both runs
- latest-answer adherence improved from `0.000` to `1.000`, context retention
  from `0.500` to `1.000`, recovery from `0.000` to `1.000`, and unnecessary
  repetition from `0.125` to zero
- contradiction failures fell from 1 to zero, deterministic failures from 14
  to zero, and qualitative failure reasons from 10 to zero; the comparison
  reports 14 fixed failures, no new failures, and no unchanged failures
- exact canonical form-state accuracy remained `1.000`, deterministic
  invention remained zero, and every value still required the existing
  proposal and explicit-confirmation boundary
- spoken whole numbers zero through twenty are normalized without a model
  call; `nobody` on a count-yourself question now asks whether the user means
  nobody else; and only one unique option match at or above the bounded
  similarity threshold can become a reviewable dropdown proposal
- explanation validation rejects both absent explicit date formats and claims
  that an unsupported partial date or estimate is acceptable; one correction
  attempt is allowed before a grounded deterministic fallback
- proposal and clarification responses are shorter, and confirm-edit responses
  explicitly acknowledge that the reviewed edit was used
- the unchanged Milestone 7.2 suite still completes all 47 turns with exact
  state `0.875`, context `1.000`, recovery `0.857`, zero repetition, zero
  invention, and only its three existing conservative occupancy-date
  presentation mismatches
- all 332 backend tests pass; the 47-turn curated transcript and 14-scenario
  safety evaluations have no failures; the frontend production build passes
  with only the existing PDF-worker bundle-size warning
- the final targeted run's average latency was higher than its baseline because
  the explanation safety check may use the existing single correction retry;
  deterministic answer turns do not add model calls

Do not implement:
- a second agent, agent debate, a new model cascade, or a stronger default model
- model-generated user scenarios or evaluation data containing real personal
  information
- automatic confirmation, direct model-to-state writes, or weaker proposal
  validation
- voice-capture changes, direct PDF interaction, final-review UI, or any
  Milestone 8 work
- authentication, persistence, analytics, a database, deployment, OCR, XFA, or
  online forms

# Milestone 7.5 — Hands-free voice interruption

Status: COMPLETE

Problem to solve:
The turn-based voice interview now continues automatically after one initial
start, but the user still has to press `Answer now` whenever they want to speak
before the assistant finishes. That push-to-interrupt pattern does not feel
like a patient helper sitting beside the user. The user should be able to begin
answering naturally, while keeping capture bounded, visible, and recoverable.

Goal:
During an explicitly active voice interview, temporarily monitor local
microphone sound levels while the assistant is speaking. Sustained user speech
stops the spoken response and opens the existing one-turn browser speech
recognition flow. Preserve `Answer now`, typed input, and every existing closed
Form Agent event as fallbacks. Do not create a second conversation or state
path.

Interaction design:
1. The user still deliberately selects `Start conversation`; no microphone is
   accessed before that action.
2. While a visible assistant response is being spoken, the UI indicates when
   hands-free interruption is being prepared, armed, or unavailable.
3. The browser analyses only transient local audio levels during that spoken
   response. It does not transcribe, buffer, upload, or persist this audio.
4. After sustained speech-like activity rather than a single noise spike, the
   assistant stops speaking and the existing one-shot speech recognizer opens.
5. The recognized utterance remains visible and follows the existing message,
   proposal, correction, skip, and explicit-confirmation flow.
6. If local interruption detection is unsupported, denied, or unreliable, the
   visible `Answer now` control and typed composer remain usable without losing
   the current question or form state.
7. Pause, end, form replacement, speech completion, recognition start, error,
   and component cleanup immediately release interruption monitoring.

Architecture boundaries:
- keep interruption detection inside the frontend browser voice adapter and
  orchestration hook
- use the browser microphone and Web Audio API only for a short-lived local
  voice-activity gate while speech synthesis is active
- use the existing one-turn Web Speech recognition only after interruption is
  detected or the user selects `Answer now`
- keep `POST /agent/respond`, typed effects, canonical conversation state,
  proposal validation, confirmation, and PDF filling unchanged
- do not send audio samples, levels, or interruption events to FastAPI,
  Nemotron, Nebius, Tavily, or the PDF service
- do not add a voice SDK, state library, backend endpoint, or dependency

Acceptance criteria:
- microphone access for hands-free interruption begins only after an explicit
  voice-session start and only while the assistant is speaking
- sustained speech-like microphone activity stops the current spoken response
  and starts exactly one existing speech-recognition turn
- short noise spikes do not trigger interruption, and a stale detector cannot
  start recognition after its assistant turn has ended
- speech completion, manual `Answer now`, pause, end, form change, error, and
  unmount stop and release the detector's stream, animation frame, audio nodes,
  and audio context
- the UI clearly distinguishes an armed hands-free interruption state from a
  preparing or unavailable fallback state
- detector permission or capability failure does not stop the interview,
  change a field, confirm a proposal, or hide `Answer now` and typed controls
- post-interruption transcripts use the same visible one-turn recognition,
  Form Agent endpoint, closed effects, and explicit-confirmation boundary as
  all other voice answers
- no audio is stored, uploaded, or transcribed during level detection
- no backend, Form Agent, PDF extraction, PDF filling, or canonical field-state
  behavior changes
- frontend production build and the existing backend, transcript, safety, and
  conversation regression checks pass

Verified implementation outcome recorded 15 October 2026:
- a dependency-free Web Audio detector now opens only while synthesized
  assistant speech is active, calibrates against the current local level, and
  requires sustained activity before dispatching one interruption callback
- a detected interruption invalidates the current speech turn, stops speech
  synthesis, releases the detector, and starts the existing one-shot Web Speech
  recognizer; it does not create a second transcript or Form Agent path
- speech completion, manual `Answer now`, pause, end, form reset, recognition
  start, detector error, stale async setup, and component cleanup all invalidate
  the detector and release its animation frame, stream tracks, source node, and
  audio context
- the assistant-speaking UI reports preparing, armed, unsupported, and failed
  interruption states while retaining `Answer now`, typed input, proposal
  controls, and explicit confirmation
- a dependency-free frontend check executes the production detector policy and
  mocked runtime, proving that calibration and short spikes cannot trigger,
  sustained activity triggers exactly once, resources close, and a detector
  stopped during asynchronous permission setup cannot later arm or fire
- the local app loaded without browser console warnings or errors; the in-app
  test browser exposed no speech or microphone APIs and therefore exercised the
  intended capability fallback rather than real-device acoustic sensitivity
- all 332 backend tests pass; the five-fixture/47-turn transcript evaluation
  and 14-scenario safety evaluation report no failures; the interruption check
  and frontend production build pass with only the existing PDF-worker
  bundle-size warning
- acoustic echo cancellation and microphone sensitivity remain browser- and
  device-dependent, so `Answer now` and typing intentionally remain permanent
  fallbacks rather than treating detector availability as a safety dependency

Do not implement:
- continuous speech recognition, always-on or background listening, wake-word
  detection, speaker identification, audio recording, or audio persistence
- server-side voice activity detection, audio upload, streaming audio, or a
  voice-specific backend endpoint
- automatic proposal confirmation, fuzzy confirmation, direct voice-to-PDF
  writes, or a second conversation state
- a voice SDK, second agent, model cascade, new model, authentication,
  persistence, analytics, a database, deployment, OCR, XFA, or online forms
- direct PDF interaction, the final-review workspace, or any Milestone 8 work

# Milestone 7.6 — Voice-first workspace redesign

Status: COMPLETE

Problem to solve:
The current frontend contains the working PDF viewer, guided interview,
proposal review, voice session, typed fallback, manual editor, and download
flow, but their presentation still resembles a generic dashboard. The large
introductory hero remains visible after a document is loaded, the assistant is
compressed into a dense rail of similarly weighted cards, important text is
small, and voice appears as one control among many rather than the primary way
to complete the form. On a mobile-sized screen the PDF is encountered before
the active interview, forcing users to scroll past the document to reach the
current question.

Goal:
Redesign the existing frontend as a calm form companion: a focused upload
experience before a document is selected and a dedicated voice-first workspace
afterwards. Keep the PDF as the main visual surface, make the assistant the
primary interaction, and use progressive disclosure for transcript history,
guidance, technical status, and manual controls. This milestone changes visual
hierarchy and responsive presentation only; it does not change the Form Agent,
voice-session policy, canonical field state, PDF behavior, or confirmation
boundary.

Design principles:
- present one obvious task and one visually dominant action for the current
  state
- make the current question, latest assistant response, and voice state readable
  at a glance
- keep the PDF prominent without allowing it to push the interview out of view
- feel like a patient person helping beside the user, not an administration
  dashboard or collection of unrelated widgets
- reveal detail when requested instead of displaying the full transcript,
  source detail, technical status, and manual editor at equal prominence
- preserve permanent typed, visible proposal-review, and manual fallbacks when
  voice is unavailable or undesirable
- use a restrained visual language: warm paper-like surfaces, dark readable
  text, one purposeful green accent, larger type, fewer borders, and limited
  motion that respects reduced-motion preferences

Experience structure:

1. Before upload:
   - show a compact Formless brand header, one plain-language value proposition,
     and one clear PDF selection action
   - use concise reassurance about local selection and review-before-apply
     behavior without turning the screen into a marketing page
   - show connection or capability problems as secondary recoverable status,
     not as the visual focus when the application is healthy
2. After upload on desktop:
   - replace the marketing hero with a compact application bar containing the
     product name, current document name, supported-field progress, and the
     contextually valid review or download action
   - use a stable two-pane workspace with approximately 58–62% of the available
     width for the PDF stage and 38–42% for the assistant
   - keep PDF page navigation associated with the document stage
   - make the assistant pane a single coherent surface rather than a vertical
     stack of equally prominent cards
   - pin the voice/session state and current question near the top and keep the
     microphone or typed composer reachable near the bottom
3. Inside the assistant pane:
   - show the current section, progress, and real active question first
   - show the latest relevant exchange without letting older turns compete with
     the current task
   - place a pending proposal immediately after the related conversation and
     keep Confirm, Edit, Use original, Reject, and Skip explicit when valid
   - distinguish listening, assistant speaking, thinking, awaiting review,
     paused, complete, unsupported, and recoverable-error states through clear
     labels and restrained visual cues
   - while the assistant is speaking and hands-free interruption is armed, show
     a concise cue that the user can speak to interrupt
   - keep the full transcript, reviewed or live guidance, and manual `Edit all
     fields` controls available through clearly labelled disclosure controls
4. On mobile:
   - provide an accessible `Assistant` / `Form` view switch instead of placing
     a tall PDF before the interview
   - default to the assistant during an active interview and keep the current
     voice/question controls within the first viewport where practical
   - retain the current PDF page and all conversation and field state when the
     user switches views
   - avoid horizontal overflow, clipped proposal controls, and fixed elements
     that obscure the composer or browser controls

State-specific primary actions:
- no document: `Choose a fillable PDF`
- document ready and voice inactive: `Start conversation`
- assistant speaking: visible speaking state with `Answer now` and the existing
  hands-free interruption cue when available
- listening: visible listening state with the existing bounded stop or cancel
  controls
- waiting for the Form Agent: one processing state without duplicate spinners
- proposal pending: explicit proposal review is primary; conversational
  acknowledgements cannot replace its controls
- paused or recoverable error: one clear resume or retry action while typing
  remains available
- form complete: canonical completion summary and existing review or download
  route, without implementing the Milestone 8 final-review workspace

Implementation plan:
- retain the existing `App` state, event handlers, API client, voice hooks,
  `PdfViewer`, and canonical field-value flow
- reorganize `frontend/src/App.tsx` into the upload and loaded-workspace modes;
  extract small presentational components only when that makes the hierarchy
  clearer and does not create duplicate state
- revise the existing design tokens and responsive rules in
  `frontend/src/index.css`; do not add a component, animation, icon, or CSS
  framework
- refine `frontend/src/VoiceAssistantPanel.tsx` so the current session state and
  primary action fit naturally into the assistant surface without changing the
  voice orchestrator or browser adapter behavior
- modify `frontend/src/PdfViewer.tsx` only if small presentational or
  accessibility adjustments are required for the new document stage; its
  rendering and page-navigation behavior must remain unchanged
- add focused dependency-free frontend checks only where new responsive view
  state or disclosure behavior could lose conversation, PDF page, or field
  state
- perform visual QA at representative laptop and mobile viewport sizes across
  upload, ready, speaking, listening, processing, proposal, error, and complete
  states using synthetic fixture data

Expected file scope:
- modify `frontend/src/App.tsx`
- modify `frontend/src/index.css`
- modify `frontend/src/VoiceAssistantPanel.tsx` if required by the final
  component boundary
- modify `frontend/src/PdfViewer.tsx` only for presentation or accessibility if
  required
- add or modify narrowly scoped frontend test/check files only if needed to
  protect new view-switch or disclosure behavior
- make no backend, PDF Service, Form Agent, prompt, evaluation-scenario, or
  dependency changes

Acceptance criteria:
- before upload, the page presents one concise purpose statement and one clear
  PDF selection action without displaying an empty application dashboard
- after upload, the introductory hero no longer consumes workspace height and
  the PDF plus assistant are visible together in the initial desktop viewport
  at a representative 1280 by 720 size
- the PDF occupies the larger desktop pane and remains the main visual surface
- the assistant's current question, voice state, and next valid action are
  visually dominant and available without searching through unrelated cards
- the loaded workspace reads as one PDF stage and one coherent companion pane,
  with substantially fewer equally weighted nested panels and badges
- the full transcript remains available but is visually secondary to the
  current exchange and is never discarded
- reviewed guidance, live guidance, provider details, and manual editing remain
  accessible but do not compete with an ordinary active question
- the typed composer remains permanently available throughout the interview
- proposal review stays visually distinct, names the question, shows original
  and prepared values when applicable, states that the PDF is unchanged, and
  retains every currently valid explicit review control
- listening, assistant speaking, interruption armed or unavailable, thinking,
  awaiting confirmation, paused, complete, unsupported, and recoverable-error
  states are distinguishable without relying on colour alone
- core question, response, input, and action text use comfortable readable
  sizing; compact metadata remains legible and is not used for essential
  instructions
- at a representative 390 by 844 mobile size, there is no horizontal overflow
  and an accessible `Assistant` / `Form` switch keeps the active interview from
  being placed below the full PDF viewport
- switching mobile views preserves the current PDF page, transcript, proposal,
  conversation phase, and canonical field values
- keyboard order and visible focus remain logical through upload, view switch,
  voice controls, conversation, proposal review, disclosures, PDF navigation,
  and the manual drawer
- status and error changes remain announced to assistive technology, controls
  retain meaningful labels, contrast remains readable, and nonessential motion
  honours reduced-motion preferences
- loading, connection, model, microphone, recognition, speech, filling, and PDF
  errors retain their existing recovery paths and do not clear user progress
- upload, extraction, typed interview, quick answers, voice session, hands-free
  interruption fallback, explicit confirmation, live preview, manual editing,
  and download continue to use the existing behavior and shared state
- no new runtime dependency is introduced
- the frontend production build, existing voice and interruption checks, and
  unchanged backend, PDF, Form Agent, transcript, safety, and conversation
  regression suites pass

Verified implementation outcome recorded 15 October 2026:
- the application now has a focused pre-upload experience with one purpose
  statement, one PDF action, concise safety reassurance, and a restrained
  paper-and-conversation visual rather than an empty dashboard
- loading a document removes the marketing hero and opens a compact application
  workspace with the PDF in the larger pane and the assistant in one coherent
  companion pane
- the loaded header contains the current filename and progress, a secondary API
  indicator and PDF replacement action, and the existing completed-PDF download
  action without duplicating download controls in the assistant
- voice status and controls, the current grounded question, the most recent
  exchange, pending proposal review, and the permanent typed composer now form
  the primary assistant hierarchy; provider detail, older transcript messages,
  sources, and manual fields remain accessible through secondary disclosures
- the typed composer remains outside the scrollable conversation region, so it
  and the collapsed manual fallback stay reachable while the current interview
  content scrolls independently
- pending proposals preserve their original/prepared comparison, unchanged-PDF
  warning, and every existing state-valid explicit review control
- small screens expose an accessible `Assistant` / `Form` switch that defaults
  to the interview; both panes remain mounted so switching does not recreate the
  PDF viewer or reset conversation and field state
- responsive measurement at 390 by 844 confirmed the selected assistant pane,
  current question, and composer are visible with document width equal to the
  viewport and no horizontal overflow
- visual QA at 1280 by 720 confirmed the PDF and assistant share the first
  viewport, the PDF holds the larger pane, and voice, the current question, and
  typed fallback remain visible together
- a dependency-free workspace layout check protects the assistant-first mobile
  default, stable pane landmarks, accessible switch targets, mounted-pane CSS,
  viewport sizing, and permanent composer placement
- no backend, Form Agent, PDF Service, prompt, model, Tavily, voice policy, or
  runtime dependency changed
- all 332 backend tests pass; the five-fixture, 47-turn transcript evaluation
  and 14-scenario safety evaluation report no failures; the workspace-layout
  and voice-interruption checks pass; and the frontend production build passes
  with only the existing PDF-worker bundle-size warning

Do not implement:
- extracted widget geometry, automatic field navigation or highlighting, PDF
  overlays, clicking a visible PDF field to edit it, or the dedicated final
  review workspace planned for Milestone 8
- any new Form Agent intent, prompt, response contract, model, Tavily policy,
  state transition, or answer-normalization behavior
- changes to microphone sensitivity, recognition, speech synthesis, hands-free
  detection, audio transport, or voice confirmation policy
- automatic or conversational confirmation, direct model-to-state writes, or
  any weakening of proposal review
- client-side PDF mutation, new extraction or filling semantics, OCR, XFA,
  scanned-form support, online forms, or free-form annotation
- authentication, persistence, analytics, a database, Docker, deployment, or
  a frontend framework, state library, component system, or new dependency
- broad rebranding, generated illustration assets, or decorative animation that
  does not support the active task

# Milestone 7.7 — Human-helper experience evaluation

Status: COMPLETE

Problem to solve:
The existing conversation harness is a strong form-state and regression tool,
but its naturalness heuristic can award a high score to short, non-repetitive,
jargon-free responses that still feel like a rigid form wizard. The current
fixed scenarios also concentrate on individual failure modes more than complete
interviews, and do not explicitly measure acknowledgement, conversational
burden, volunteered-fact retention, side-question recovery, unnecessary
workflow pressure, or suitability for spoken delivery. A fluent qualitative
judge must not be allowed to hide an incorrect form effect or unsafe state.

Goal:
Extend the test-only conversation harness with a separate human-helper
experience suite and two visible gates. The correctness gate remains
authoritative over form state, grounding, and confirmation. The human-helper
gate measures whether the same safe workflow behaves like a patient person
completing the form beside the user. Establish the current-agent baseline
before making any new production conversation changes.

Evaluation architecture:
- retain every existing Milestone 7.2 and 7.4 scenario unchanged
- keep all new code, scenarios, scoring, judging, and reports under
  `backend/evaluations`; production code must never import evaluation code
- drive the unchanged public `FormAgentService.respond` or `POST
  /agent/respond` boundary over schemas extracted from checked-in PDF fixtures
- add observable per-turn behavioural checks instead of matching one exact
  assistant sentence
- record each behavioural result and failure beside the existing event,
  request state, typed effect, response state, field state, latency, and error
- allow deterministic scripted branches based on the previous visible message,
  typed effect, or expectation outcome so a synthetic user can challenge an
  unhelpful response while runs remain reproducible
- retain suite digests and compare only identical versioned suites
- add an optional blinded pairwise judge that sees transcript A and transcript
  B without baseline/candidate labels; qualitative preference cannot override
  an incorrect deterministic result
- do not add an autonomous model-generated user because changing user output
  would weaken before/after reproducibility

Human-helper measurements:
- volunteered-fact recall rate
- redundant-question rate
- side-question recovery rate
- unnecessary workflow-push rate
- acknowledgement rate
- clarification-success rate
- interruption-recovery rate
- speech-suitability rate
- overall observed human-helper behaviour rate
- turns per confirmed field
- optional judged human-helper resemblance

Gate policy:
- correctness requires every scheduled turn to complete, exact expected
  canonical form state, zero ungrounded proposals or claims, zero confirmation-
  boundary failures, and zero transcript/state contradictions
- human-helper behaviour is reported separately and cannot compensate for a
  failed correctness gate
- the human-helper gate requires at least 80% success on each scored positive
  behaviour, at most 10% redundant questions and unnecessary workflow pushes,
  and at least 4/5 judged human-helper resemblance when the optional judge is
  enabled
- the older heuristic naturalness metric remains visible for compatibility but
  no longer treats surface fluency as sufficient for a perfect score

Required scenario coverage:
- complete multi-field conversations rather than isolated responses
- multiple volunteered facts and explicit objections to being asked twice
- explanations that become progressively simpler
- ambiguous and incomplete values followed by focused clarification
- side questions answered before returning to the form
- interruptions, pauses, progress questions, and resumption
- frustration and requests to slow down
- skipping, reopening, corrections, rejection, and post-completion review
- concise voice-style exchanges and response-length pressure
- synthetic personal information only

Acceptance criteria:
- the versioned suite contains at least 10 synthetic personas, 12 long-form
  scenarios, 150 scheduled turns, and four real checked-in PDF fixtures
- scenario fields are resolved from actual extraction results rather than a
  duplicate hand-written production schema
- behavioural expectations cover acknowledgement, relevant answers, returning
  to the active field, focused clarification, known-information re-asks,
  unnecessary advancement, question burden, and spoken-response suitability
- deterministic branching is covered by tests and the selected branch is saved
  in the transcript artifact
- reports expose both gates, every new aggregate metric, per-turn behavioural
  results, and stable failure reasons
- turns-per-confirmed-field is calculated from actual confirmed effects rather
  than scenario declarations
- qualitative judging scores attentiveness, helpfulness, conversational flow,
  adaptability, user effort, and human-helper resemblance
- one command can make a blinded pairwise qualitative comparison of matching
  baseline and candidate reports
- old report files remain loadable and the old suites remain valid
- normal tests use deterministic doubles and make no network requests
- a baseline of the unchanged current Form Agent is saved before any production
  behaviour is modified
- focused harness tests and the complete existing backend checks pass

Verified implementation outcome recorded 15 October 2026:
- the new `human-helper-experience-v1` suite contains 12 synthetic personas,
  14 long-form scenarios, and 182 scheduled turns over the sample,
  household-support, USCIS I-9, SBA startup-cost, and State Department DS-11
  fixtures
- scenarios exercise multi-fact retention, repeated-question resistance,
  progressive explanation, ambiguity, side questions, interruption, emotion,
  skipping, reopening, correction, rejection, review, and spoken brevity
- per-turn observable behaviour results and deterministic branch selection are
  retained in JSON and Markdown artifacts alongside existing state evidence
- reports separate a hard correctness gate from the human-helper gate and
  expose conversational burden and all named human-helper rates
- optional qualitative scoring now includes the human-helper dimensions, and
  the `pairwise` command performs label-blinded comparison with deterministic
  scenario ordering
- the unchanged live current-agent baseline recorded 144 of 182 scheduled turns,
  0.572 exact form-state accuracy, 0.433 side-question recovery, 0.442
  unnecessary-push rate, 0.708 acknowledgement, 0.500 clarification success,
  1.000 speech suitability, 0.812 observed behaviour, and 0.730 scheduled-check
  coverage; both gates failed while invention and confirmation-boundary
  failures remained zero
- the checked-in baseline summary records the largest weaknesses while full
  synthetic transcript artifacts remain ignored locally
- production Form Agent, PDF, frontend, voice, dependency, and API behaviour
  remain unchanged
- all 334 backend tests pass; the existing five-fixture/47-turn transcript and
  14-scenario safety evaluations report no failures

Do not implement:
- production prompt, conversation-policy, field-adapter, state-machine,
  frontend, voice, PDF extraction, or PDF filling changes
- exact-string requirements for otherwise valid conversational prose
- model-generated personas or real personal information
- production analytics, transcript persistence, browser storage, a database,
  authentication, or deployment infrastructure
- a second production agent, model cascade, agent framework, or automatic
  confirmation
- Milestone 8 direct PDF interaction or final-review work

# Milestone 7.8 — Targeted human-helper conversation repairs

Status: COMPLETE

Problem to solve:
The fixed Milestone 7.7 baseline shows that the assistant remains safe but does
not yet consistently behave like a patient person filling in the form beside
the user. It can lose later facts volunteered in a multi-answer message, retain
conversational wrappers or sentence punctuation as field values, mistake a
question about the active field for navigation, give a generic completion
message when the user asks a specific review question, and push the workflow
before clearly acknowledging or resolving the user's latest concern.

Goal:
Make the smallest evidence-backed production changes that repair those observed
conversation failures while preserving one Form Agent, bounded request state,
closed typed effects, explicit confirmation, canonical frontend field state,
and the rule that the user is the only source of personal facts.

Targeted conversation changes:

1. Bounded volunteered-answer memory
   - separate the active answer from explicitly cued answers for later real
     fields when a user supplies several facts in one message
   - retain at most a small fixed number of validated, unconfirmed candidates
     in the request-carried conversation state, tied to stable field IDs and
     their original user wording
   - capture a later candidate only when one real field and one compatible value
     can be identified with high confidence; otherwise leave it unrecorded and
     ask a focused clarification when that field becomes active
   - when a remembered field becomes active, present its candidate as a normal
     reviewable proposal instead of asking the user to repeat it
   - never treat a remembered candidate as confirmed, write it to canonical
     form state, or send it to the PDF Service without explicit confirmation
   - clear or replace remembered candidates deterministically after review,
     skip, correction, form replacement, or other relevant state transitions

2. Conservative conversational-wrapper cleanup
   - extend field-type adapters to isolate the value in phrases such as
     `My surname is Okafor.` and `I am back. It is J.`
   - remove terminal sentence punctuation only when it is clearly prose around
     a compatible candidate; preserve meaningful internal punctuation,
     apostrophes, hyphens, abbreviations, email addresses, and identity spelling
   - keep the original candidate, prepared value, and visible transformation
     explanation whenever cleanup changes the proposed text
   - do not add speculative spelling correction or general-purpose prose
     rewriting to factual fields

3. Active-field side-question recovery
   - classify a direct informational question about the active field before
     attempting global field-reference or navigation matching
   - ground pronouns and field-local wording in the active question, bounded
     schema metadata, and verified guidance already allowed by the architecture
   - answer the question without proposing a value, retain the active field,
     then return naturally to it without repeating an unnecessary menu
   - if the available context cannot support the answer, say what is unknown
     and ask one useful clarifying question rather than inventing a rule

4. Post-completion review and correction
   - evaluate specific review, status, and correction intent before returning a
     generic form-complete response
   - answer questions about confirmed, skipped, and unanswered fields from
     canonical state, including a specific field's stored status or value
   - start an existing closed correction transition when the user asks to
     replace a confirmed value; keep the confirmed value until the replacement
     is explicitly confirmed
   - reserve the generic completion response for genuinely general next-step
     requests

5. Acknowledge, answer, then progress
   - make the assistant respond first to the user's latest concern, confusion,
     interruption, or frustration
   - use one concise acknowledgement when useful, answer the concern, and only
     then return to the active question
   - avoid repeated workflow instructions, premature advancement, and generic
     `all fields reviewed` messages in response to a specific question
   - keep ordinary responses suitable for spoken delivery without enforcing one
     exact sentence or making the model's prose authoritative over state

Implementation boundaries:
- keep the existing Form Agent as one public service and place routing, state,
  adapter, prompt, and parsing changes in their existing focused modules
- any remembered candidate is bounded ephemeral conversation state supplied in
  requests; it is not persistence, canonical form data, or model memory
- deterministic field identification and field-type validation remain
  authoritative; Nemotron may help phrase or interpret an ambiguous turn but
  cannot create a candidate for a field the user did not answer
- all form-changing outcomes remain closed typed effects and use the existing
  proposal, replacement, confirmation, rejection, skip, and correction paths
- the frontend may transport and validate the expanded conversation state, but
  this milestone does not redesign the workspace or add new visible controls

Evaluation method:
- preserve `human-helper-experience-v1` and its recorded suite digest unchanged
  so the live candidate is compared with the existing baseline on identical
  personas, fixtures, turns, branches, and behavioural expectations
- add focused deterministic and transcript tests for every repaired failure,
  including bundled answers, `Okafor.`, `I am back. It is J.`, an active-field
  `Do I count myself?` question, and specific post-completion review/correction
- save the candidate report and compare it with the checked-in baseline; report
  both hard correctness and human-helper gates rather than relying on a single
  aggregate score
- do not tune to exact assistant sentences or alter a failing expectation merely
  to make the candidate appear better

Acceptance criteria:
- one multi-field message can produce the active field proposal and retain
  uniquely identified later candidates without confirming any of them
- progression to a remembered field offers the retained value for explicit
  review rather than asking the same factual question again
- ambiguous, incompatible, duplicate, or uncued values are not silently stored
  as remembered candidates
- conversational wrappers and safe terminal punctuation are removed in the
  covered field types while meaningful identity punctuation is preserved
- a question about the active field is answered before any navigation or value
  interpretation, leaves canonical values unchanged, and returns to the same
  field
- form-complete review questions list or describe confirmed, skipped, and
  unanswered fields accurately from canonical state
- post-completion correction uses the existing replacement proposal and
  explicit-confirmation boundary
- all newly introduced conversation state has a strict size bound, validates
  against the supplied schema, and is accepted and returned consistently by
  the backend and frontend
- the unchanged human-helper suite passes its correctness gate and human-helper
  gate, including zero invention and confirmation-boundary failures
- the existing five-fixture transcript evaluation, 14-scenario safety
  evaluation, backend test suite, voice and interruption checks, and frontend
  production build pass without regression

Verified implementation outcome (16 October 2026):
- request-carried conversation state can retain at most five unique,
  schema-valid, adapter-compatible, unconfirmed candidates for later fields;
  an explicit reference to an earlier answer offers the candidate through the
  normal proposal and confirmation path
- deterministic adapters now isolate the covered volunteered names, dates,
  dropdown choices, spoken counts, and conversational wrappers while retaining
  original wording and a visible transformation when preparation changes the
  proposed value
- active-field informational questions, requests for simpler wording, and
  frustration are handled before navigation or answer interpretation and do
  not mutate canonical form values
- completion-time summaries, specific stored-value questions, field reopening,
  correction, replacement rejection, and cancellation are resolved from
  canonical state through closed effects; a rejected replacement leaves the
  existing confirmed value unchanged
- the unchanged `human-helper-experience-v1` suite digest
  `2529802e73125ede` completed all 182 turns across 14 scenarios with 1.000
  form-state accuracy, volunteered-answer recall, side-question recovery,
  acknowledgement, clarification success, and interruption recovery; invention,
  contradiction, deterministic, and confirmation-boundary failures remained
  zero, and both gates passed
- all 352 backend tests pass; the five-fixture/47-turn transcript evaluation
  and 14-scenario safety evaluation report no failures; the frontend production
  build, workspace-layout check, and voice-interruption check pass
- PDF extraction/filling, voice capture, model selection, persistence, and the
  Milestone 8 workflow were not changed

Expected implementation files:
- `backend/app/services/form_agent/models.py`
- `backend/app/services/form_agent/orchestrator.py`
- `backend/app/services/form_agent/conversation_policy.py`
- `backend/app/services/form_agent/answer_adapters.py`
- `backend/app/services/form_agent/answer_preparation.py`
- `backend/app/services/form_agent/prompt_builder.py` only if bounded side-
  question context needs adjustment
- focused backend Form Agent and transcript tests
- `frontend/src/App.tsx` only for expanded conversation-state transport and
  validation
- evaluation artifacts and source-of-truth documentation after verification

Do not implement:
- a second agent, runtime model cascade, model debate, autonomous planning, an
  agent framework, or a model-generated user
- automatic confirmation, silent application of remembered answers, direct
  model-to-state writes, or any weakening of proposal review
- unbounded chat history, server-side transcript storage, browser persistence,
  analytics, authentication, a database, or user profiling
- broad spell correction, inferred personal facts, form-specific answer hacks,
  or Tavily searches containing user answers
- voice-capture changes, a frontend redesign, direct PDF field interaction,
  PDF extraction or filling changes, OCR, XFA, or Milestone 8 review work

# Milestone 8 — Full workflow

Status: COMPLETE

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

Verified implementation outcome recorded 16 October 2026:
- AcroForm extraction now returns every discovered widget as a one-based page
  number plus normalized top-left `x`, `y`, `width`, and `height` coordinates,
  tied to the existing stable field ID; repeated widgets remain associated with
  the same field
- the custom PDF viewer renders a coordinate overlay without mutating the PDF
  in the browser, follows the active assistant field to its page, and visibly
  distinguishes active, selected, proposed, completed, skipped, and unanswered
  fields
- selecting a supported widget opens an in-context editor; direct edits, the
  existing manual drawer, and confirmed Form Agent effects all write through
  the same `formValues`, confirmation, skip, and preview state
- the manual drawer remains closed by default, while switching among the
  assistant, PDF editor, review panel, and manual drawer preserves current
  values by stable field ID
- final review lists completed, proposed, skipped, and unanswered fields and
  lets the user return directly to a field on the document
- unconfirmed drafts and agent proposals never enter the `/pdf/fill` payload;
  clearing or skipping a changed value removes it from that payload, and a
  confirmed direct or manual change uses the existing debounced backend fill
  and download flow
- normalized geometry is asserted against the small PDF fixture and checked on
  the SBA fixture; all 352 backend tests, the five-fixture/47-turn transcript
  evaluation, the 14-scenario safety evaluation, the frontend production build,
  PDF-workflow check, workspace-layout check, and voice-interruption check pass
- the app was smoke-tested in the browser at desktop size with a healthy
  backend connection; automated local-file attachment was unavailable in that
  browser surface, so loaded-document positioning remains covered by fixture
  coordinate assertions and the focused frontend workflow check
- no AI, voice, guidance, authentication, persistence, database, OCR, XFA,
  online-form, PDF-filling-semantic, or dependency changes were introduced

# Milestone 9 — Polish and reliability

Status: COMPLETE

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

Completed reliability repair — self-interruption during spoken replies:
- while the assistant begins speaking, calibrate the local activity gate
  against speaker-to-microphone leakage before hands-free interruption arms
- request browser echo cancellation and noise suppression while disabling
  automatic gain control so quiet playback leakage is not amplified into a
  false interruption
- require sustained, varying speech-like activity above both the ambient-noise
  threshold and calibrated playback-leakage ceiling before cancelling speech
- keep `Answer now`, typed input, and the existing bounded listening turn as
  permanent fallbacks when a quiet user interruption cannot be distinguished
  safely from playback
- deterministically test calibration, playback leakage, short spikes,
  non-speech sound, genuine sustained voice activity, single dispatch, and
  resource cleanup

Completed maintainability repair — behavior-preserving frontend split:
- retain canonical form, confirmation, skip, proposal, conversation, and PDF
  preview state in the existing `App` orchestration boundary
- move shared TypeScript contracts, API-response validation, field-state
  helpers, and reusable field controls into focused dependency-free modules
- move the header, upload view, document workspace, active-question card,
  transcript, proposal review, final review, and manual drawer into
  presentational components that receive state and callbacks from `App`
- keep fetch behavior, API payloads, PDF and voice behavior, visible copy,
  DOM state landmarks, and all safety boundaries unchanged
- update focused frontend checks to follow the new component ownership instead
  of requiring every workflow element to live physically in `App.tsx`

Completed maintainability repair — behavior-preserving Form Agent policy split:
- retain `conversation_policy` as the stable import surface used by the
  orchestrator, prompt builder, guidance modules, and existing tests
- move turn classification and explanation-repair context to `intent_policy`
- move model-action safety checks to `action_validation`
- move allowed event transitions, conversation-state changes, and closed typed
  effect construction to `state_machine`
- move field selection, correction, progress, completion, and clarification
  responses to `navigation_policy`
- keep deterministic per-turn routing, failure fallbacks, and message
  normalization in `conversation_actions`
- preserve every existing non-private `conversation_policy` import, request and
  response contract, prompt, model call path, message, transition, and effect
- make no PDF Service, frontend, provider, dependency, or evaluation-scenario
  changes as part of the split

Verified outcomes recorded 16–17 October 2026:
- the interruption gate now calibrates for 900 ms, retains the observed
  playback-leakage ceiling, and requires at least 420 ms, five active samples,
  three speech-like samples, and meaningful level variation before dispatch
- the microphone request keeps echo cancellation and noise suppression enabled
  but turns automatic gain control off
- the focused interruption policy check proves that changing playback leakage
  does not interrupt, a short spike does not interrupt, sustained non-speech
  activity does not interrupt, and sustained varying voice activity dispatches
  exactly once and releases its resources
- connection, extraction, and completed-preview failures expose explicit retry
  controls; retries reuse the retained PDF and canonical confirmed values
  rather than asking the user to start over
- the original PDF remains visible when extraction returns no supported fields
  or fails, and the interface explains that only fillable AcroForm fields can
  be edited while preserving the `Change PDF` path
- connection and progress state use live regions, unavailable download state is
  a real disabled control, the PDF overlay and page navigation remain named
  buttons, and the manual drawer exposes its controlled region and open state
- the direct PDF editor and final review support Escape, receive or restore
  keyboard focus deliberately, and visible focus styling covers PDF targets,
  review, recovery, and editor controls
- direct or manual correction updates the one canonical value, confirmed-ID,
  skipped-ID, preview, and confirmed-only fill-payload path; clearing a value
  removes its previous confirmation before download
- rendered checks at 1440 by 900 and 390 by 844 show no horizontal overflow;
  the phone layout retains an explicitly named connection status even when its
  visible label is compacted
- `App.tsx` was reduced from 3,508 to 1,349 lines and now concentrates on
  ephemeral session state, cross-mode orchestration, and application assembly;
  shared contracts, strict agent-response parsing, field-state policy, field
  controls, and major presentation sections have focused owners
- all extracted components remain controlled by `App`: they do not fetch,
  duplicate canonical values, infer agent effects, fill PDFs, or create a
  second voice or conversation path
- no runtime dependency, backend contract, visible workflow, PDF behavior,
  Form Agent behavior, voice policy, or styling changed during the split
- the PDF-workflow, workspace-layout, and voice-interruption checks and the
  frontend production build pass after the split; all 353 backend tests also
  pass with only the existing five PyMuPDF/SWIG deprecation warnings
- the previous 2,103-line `conversation_policy.py` is now a 55-line stable
  compatibility surface; its implementation is separated into focused intent,
  action-validation, state-machine, navigation, and deterministic-action
  modules, with no policy implementation file over 716 lines
- the compatibility test proves the established policy imports resolve to the
  new focused owners, while callers continue to use the same module surface
- the unchanged five-fixture, 47-turn transcript evaluation retains its exact
  baseline metrics and zero failures, including zero invalid actions, invalid
  proposals, confirmation-boundary failures, unsafe transformations, invented
  facts, and invented purposes
- no Form Agent API, prompt, user-visible response, state transition, closed
  effect, model call path, PDF behavior, frontend behavior, or dependency was
  changed by the backend split
- one API-level regression test now takes the sample, household-support, SBA,
  DS-11, and I-9 fixtures through extraction and filling, reopens every result
  with `pypdf`, checks the stored value, and proves the source bytes are
  unchanged
- the Milestone 9 frontend reliability check covers retry ownership, canonical
  correction state, keyboard semantics, focus recovery, screen-reader labels,
  responsive recovery controls, and reduced motion
- the final verification passes all 358 backend tests, the PDF-workflow,
  workspace-layout, voice-interruption, and Milestone 9 reliability checks,
  and the frontend TypeScript/Vite production build; the only warnings are the
  existing five PyMuPDF/SWIG deprecations and Vite's non-failing bundle-size
  advisory

# Future milestone sequence

The base Milestones 1 through 9 are complete. The later Milestones 9.1, 9.1.1,
9.2, and 9.2.1 have implementation evidence recorded above, with the named
manual/live work still open where their status says so. The remaining product
work must follow this order so conversation meaning, voice turn-taking, and
layout can be tested separately before they are judged together:

1. Milestone 9.2.2 — Context-rich Nemotron conversation and natural review
2. Milestone 9.2.3 — Continuous hands-free voice session
3. Milestone 9.2.4 — Fixed-viewport conversational workspace
4. Milestone 9.2.5 — Integrated human-helper workflow validation
5. Milestone 9.3 — One-language bilingual assistance pilot, only if its go/no-go
   gate passes and does not displace release validation
6. Milestone 9.4 — Hero workflow validation and release freeze
7. Milestone 10 — Deployment
8. Milestone 11 — Hackathon submission

Sequencing rule recorded 29 October 2026:
- implement and evaluate one of Milestones 9.2.2 through 9.2.4 at a time
- do not hide a failed conversation, voice, safety, or layout criterion by
  combining all three changes in one unmeasured implementation pass
- Milestone 9.2.5 is the mandatory integration gate before hero-workflow freeze
- because these are substantive product changes immediately before the stated
  deadline, defer Milestone 9.3 rather than weakening safety, testing, release,
  deployment, or submission evidence if time is insufficient
- deadline pressure does not authorize skipping explicit confirmation, live
  provider checks, source-PDF preservation, or the no-invention boundary

Milestones 12 onward are a deferred post-hackathon roadmap. They are recorded
so near-term architecture does not block the product direction, but they are
not authorized by completing a current milestone.

## Test policy for every remaining milestone

A milestone is complete only when all of the following are true:
- its focused automated tests pass
- the unchanged backend, PDF, Form Agent, frontend, transcript, safety, and
  human-helper checks relevant to its scope still pass
- the named manual test has been performed with synthetic personal data
- acceptance evidence and any known limitation are recorded in this plan
- a failed safety, confirmation, canonical-state, or no-invention check blocks
  completion even when the conversation sounds good
- live provider evaluation is required only when the milestone changes or
  deploys provider-dependent behaviour; ordinary automated tests must remain
  deterministic and network-free

The established local regression gate is:

```bash
cd backend
.venv/bin/python -m pytest
PYTHONPATH=. .venv/bin/python -m evaluations.form_agent_evaluation
PYTHONPATH=. .venv/bin/python -m evaluations.form_agent_transcript_evaluation

cd ../frontend
npm run test:pdf-workflow
npm run test:workspace-layout
npm run test:voice-interruption
npm run test:milestone9-reliability
npm run build
```

Milestones may add one focused command to this gate. Do not remove or weaken an
existing check simply to make a new milestone pass.

# Milestone 9.1 — Support-aware introduction and adaptive assistance

Status: IMPLEMENTED — MANUAL LOADED-FORM QA PENDING

Why this is next:
Formless currently starts with the form's first question. A person helping
beside the user would first ask how to make the task easier. This milestone
adds that small introduction without profiling the user, diagnosing a
condition, or changing the form's factual and safety rules.

Goal:
After extraction and before the first field, offer an optional, brief
introduction that lets the user choose how they want help. Use those choices to
adapt wording, pacing, explanation depth, and the preferred interaction mode
for the current form session only.

Scope:
- begin in an explicit `support_setup` conversation phase before selecting the
  first form field
- ask one open question such as `What tends to make forms difficult for you?`
- accept a natural spoken or typed answer, then ask at most one focused
  follow-up about speaking, typing, or either when that remains unclear
- offer needs rather than identity or diagnosis labels, including:
  - use simpler language
  - go slowly and ask one thing at a time
  - let me speak rather than type
  - help me organise the details I already have
  - reassure me before important changes
  - explain unfamiliar form or bureaucracy language
  - something else, using one short bounded note
  - skip this and begin the form
- optionally ask whether the user would rather speak or type; never start the
  microphone as a consequence of selecting a preference
- let the user say `just start` at either support step and immediately ask the
  first form question with standard or already-selected help
- keep the checkbox/radio preference panel collapsed behind `Adjust how I
  help` as an optional direct fallback, not the primary introduction
- keep a small validated assistance-preference object in the current
  request-carried session state
- allow preferences to be reviewed or changed during the session
- clear preferences when the user changes PDF or starts a new form
- adapt only presentation: tone, response length, pacing, explanation depth,
  and whether voice is visually emphasised
- keep field selection, answer interpretation, validation, proposals,
  confirmation, guidance eligibility, canonical values, and PDF filling
  unchanged
- use supportive language without claiming that the system has identified a
  disability, language level, legal status, or personal category

Architecture boundaries:
- `App` remains the current-session owner and the Form Agent remains the single
  conversation service
- preferences are explicit bounded data, not a model-inferred profile, hidden
  memory, analytics record, database record, or personal fact
- the Form Agent owns the explicit setup phase and deterministically maps only
  clear user requests into the bounded preference schema
- conversation preference changes return a closed validated effect; model
  prose cannot create a preference or a form mutation
- the frontend presents the conversation and applies only that effect or an
  explicit direct-settings change
- no preference can cause a model response to write or confirm a form value
- the architecture may reserve an explicit assistance-language value with
  English as the only supported value, but must not expose unsupported language
  choices before Milestone 9.3

Acceptance criteria:
- introduction is conversational, optional, skippable, keyboard accessible,
  and works through both the existing typed and voice interview paths
- a clear natural-language need updates only supported preferences, receives a
  natural acknowledgement, and progresses without displaying a questionnaire
- an ambiguous difficulty or disclosed condition produces a neutral follow-up
  and is not stored as a diagnosis, profile, or inferred preference
- the direct preference controls start collapsed under `Adjust how I help`
  and do not block the PDF-click or manual workflows
- each supported choice produces a visible and relevant presentation change
  without changing the expected form effect or canonical field state
- the free-text support note has a strict length limit, is treated as untrusted
  context, and cannot override system, safety, validation, or confirmation
  policy
- preferences are session-only, editable, and cleared on form replacement
- selecting voice preference does not request microphone permission or begin a
  voice session
- direct PDF edits, manual edits, and confirmed agent effects still share one
  canonical state
- no diagnosis, protected characteristic, or unsupported personal fact is
  inferred or stored
- existing workflows still work when the introduction is skipped

Required automated testing after implementation:
- backend contract tests for every allowed preference, unsupported values,
  duplicate values, overlong free text, and prompt-injection-shaped text
- prompt tests proving preferences are bounded untrusted presentation context
  and cannot alter available fields, options, effects, or confirmation rules
- paired transcript tests that send the same factual answers with and without
  each preference and assert identical typed effects and final canonical state
- conversation tests for the open question, needs acknowledgement, interaction
  follow-up, `just start`, interaction-first answers, ambiguous conditions,
  prompt-injection-shaped text, and explicit mid-form preference changes
- state/effect tests proving support setup cannot create, confirm, skip, or
  otherwise modify a PDF field
- frontend focused checks for the initial setup phase, strict preference-effect
  parsing, collapsed direct controls, optional/skip/edit/clear behaviour,
  keyboard and screen-reader order, focus restoration, laptop/mobile layout,
  and the rule that voice preference does not start microphone capture
- the complete established local regression gate

Required manual testing after implementation:
1. Open the sample and household-support fixtures in separate fresh sessions.
2. Start once with typing and once with voice; verify the assistant asks what
   feels difficult before it asks the first form question.
3. Complete one session by saying `just start` and another by naturally asking
   for simple language and one question at a time.
4. Give an ambiguous condition or difficulty statement and verify the assistant
   asks what adjustment would help without storing or repeating a diagnosis.
5. Open `Adjust how I help`, change preferences halfway through, and verify the
   next response adapts while the controls remain collapsed afterward.
6. Choose voice preference and verify no microphone prompt appears until
   `Start conversation` is explicitly selected.
7. Replace the PDF and verify the earlier preferences are gone.
8. Confirm that identical user facts produce identical stored PDF values in all
   runs.

Completion evidence to record:
- focused test names and results
- full regression results
- two short synthetic transcripts showing different presentation but the same
  typed effects and canonical values
- desktop and mobile introduction screenshots
- any preference that could not be made reliably observable

Do not implement:
- diagnosis, demographic classification, automatic language detection, user
  accounts, persistent profiles, analytics, a database, or server-side memory
- a second agent, a new model, autonomous planning, or changes to PDF semantics
- Milestone 9.2 speech-provider work, Milestone 9.3 language output,
  deployment, or submission work

Implemented outcome refined 18 October 2026:
- a fresh frontend session now begins in the explicit `support_setup` phase;
  the first assistant response asks what tends to make forms difficult instead
  of displaying preference checkboxes
- clear natural requests for simpler wording, slower pacing, organisation,
  reassurance, or explanation of official wording are mapped deterministically
  into the existing closed preference object; the next focused turn asks
  whether speaking, typing, or either is preferred when necessary
- an interaction preference supplied first is retained while the assistant asks
  what support would help; `just start` at either step immediately selects the
  first unanswered field
- ambiguous statements and condition disclosures receive a neutral needs-based
  follow-up; tests prove they are not stored as a diagnosis or passed to
  Nemotron for profile inference
- conversational changes use the new validated
  `assistance_preferences_updated` effect; the effect cannot propose, confirm,
  skip, or write a form value, and mid-form changes preserve the active field
  and any pending proposal
- `App` remains the session owner, applies only validated preference effects,
  sends the resulting preferences with later Form Agent requests, and clears
  them with all other form state on replacement
- the checkbox/radio controls now start collapsed behind `Adjust how I help`;
  they remain an accessible direct fallback over the same preference object and
  still cannot start microphone capture; keyboard focus moves into the editor
  when it opens and returns to the adjustment button when it closes
- the original closed request validation, 200-character untrusted custom note,
  prompt boundary, identical-effect parity, canonical field state, and explicit
  confirmation rules remain unchanged
- all 385 backend tests pass with only the existing five PyMuPDF/SWIG warnings;
  the 14-scenario safety evaluation and five-fixture/47-turn transcript
  evaluation have no failures, zero invalid actions or proposals, zero unsafe
  transformations, and zero invention or confirmation-boundary failures
- PDF workflow, workspace layout, voice interruption, Milestone 9 reliability,
  and conversational support-preference frontend checks pass; the production
  build succeeds with only the existing non-failing bundle-size advisory
- the required loaded-form desktop/mobile conversational, skip, adjustment,
  reset, and voice-permission checklist and screenshots remain pending

Do not mark this milestone complete until the required manual loaded-form steps
above have been performed with the sample and household-support fixtures.

# Milestone 9.1.1 — Natural-language turn interpretation

Status: IMPLEMENTED — MANUAL QA PENDING

Why this is next:
The deterministic adapters are reliable for recognized phrases but can be too
literal. A user may state the same fact conversationally, answer a checkbox
without saying exactly `yes`, describe a dropdown option in ordinary words,
correct themselves, or supply several facts together. When those turns fall
outside narrow patterns, the assistant may repeat the question or ask the user
to adopt its wording. Better speech recognition will not fix an accurately
transcribed turn that the Form Agent does not understand.

Goal:
Interpret natural typed or transcribed turns through one bounded Nemotron
schema, then pass every candidate through the existing field adapters,
normalization, proposal review, and explicit confirmation boundary. The user
should be able to speak naturally without giving Nemotron authority to write
form state or PDF bytes.

Target flow:

```text
natural user turn
    -> bounded Nemotron turn interpretation
    -> deterministic field adapter and value validation
    -> focused clarification when uncertain or invalid
    -> ordinary typed proposal effect
    -> explicit user confirmation
    -> canonical field state
    -> existing PDF filling path
```

Scope:
- establish a fixed paraphrase-heavy baseline against the existing public Form
  Agent interface before changing production interpretation
- introduce one closed structured interpretation containing an intent,
  confidence, clarification flag, and only user-grounded candidate data
- distinguish answer, correction, explanation request, uncertainty,
  multi-field answer, unrelated conversation, explicit assistance preference,
  skip request, and return-to-field reference
- allow a candidate only for a supplied real field ID and preserve bounded
  evidence from the current user turn
- use the latest turn as authoritative; history may resolve references but may
  not replace the current answer
- send interpreted candidates through existing field-specific adapters and
  validators; invalid or ambiguous candidates produce a specific clarification
- keep exact deterministic commands and already-unambiguous values on their
  current fast path when semantic interpretation is unnecessary
- permit conversational dropdown or checkbox paraphrases only when the model
  returns one valid closed value with sufficiently high confidence; every
  result remains an unconfirmed visible proposal
- retain at most five validated later-field candidates through the existing
  request-carried remembered-candidate state when several facts are supplied
- use interpreted skip, navigation, correction, and assistance intents only as
  input to deterministic policy; interpretation cannot emit a public effect
- fall back safely to the existing clarification or action path when an
  interpretation is malformed, low-confidence, unsupported, or unavailable
- preserve names, identifiers, negation, uncertainty, and the user's evidence;
  do not silently repair spelling or manufacture missing precision
- keep the frontend and voice adapter unchanged; both already send the same
  message event into the Form Agent

Examples the fixed suite must cover:
- `I get overwhelmed, so take it slowly.`
- `Talk me through the official wording.`
- `I'd rather just explain things in my own words.`
- `Yeah, that applies to me.`
- `It was the seventeenth of October 1986.`
- `Actually, use my current address instead.`
- `My first name is Ibrahim, surname Akhoon.`
- `I'm employed full-time.` when the form exposes an `Employed` option
- one message that supplies the active answer and one later-field answer
- uncertainty that must remain a clarification rather than becoming a guess

Architecture boundaries:
- this remains one Form Agent and one Nemotron model behind the existing
  Nemotron Service; it is not a second agent or an agent debate
- the interpreter owns semantic classification only; it cannot return public
  effects, change conversation state, call Tavily, call the PDF Service, or
  fill a PDF
- orchestration owns when interpretation is needed and converts only validated
  results into existing actions
- field adapters and value normalization remain deterministic authorities over
  valid stored values and exact dropdown options
- the state machine remains the only owner of public effects and transitions
- explicit confirmation remains mandatory for every interpreted factual value
- malformed structured output receives no broader authority than the existing
  controlled model-repair and fallback path

Acceptance criteria:
- a versioned synthetic suite groups at least 10 natural paraphrases across
  names/free text, dates, numbers, checkboxes, dropdowns, uncertainty,
  corrections, explanation requests, skips, and multi-field answers
- a saved baseline records current acceptance, clarification, repetition,
  invalid-action, invention, and confirmation-boundary results before the
  production change
- every successful interpretation uses a closed validated schema and references
  only supplied real field IDs
- semantically equivalent paraphrases produce the same prepared candidate or
  the same safe clarification after deterministic validation
- an unknown, incompatible, invalid-option, ungrounded, or low-confidence model
  candidate cannot become a proposal
- no interpreted value enters canonical field state before its matching
  explicit confirmation event
- a correction preserves the currently confirmed value until a replacement is
  explicitly confirmed
- multi-field turns retain only bounded, uniquely mapped, adapter-valid later
  candidates and cannot confirm any of them implicitly
- explanation, unrelated-conversation, skip, navigation, and assistance intents
  do not accidentally become factual proposals
- provider failure leaves the active question and canonical form state intact
  and gives a usable clarification or established fallback
- the candidate evaluation materially improves paraphrase acceptance or reduces
  avoidable clarification/repetition relative to the fixed baseline without
  increasing invention, invalid-action, or confirmation-boundary failures
- existing PDF, guidance, conversation, frontend, voice, safety, and
  human-helper regression gates remain green

Required testing:
- parser tests for every intent, missing and contradictory properties, extra
  keys, unknown fields, duplicate or excessive candidates, malformed JSON, and
  prompt-injection-shaped user text
- orchestration tests proving deterministic fast paths remain deterministic and
  conversational answers use interpretation only when needed
- field-type tests for natural names, spoken dates, numbers, checkbox phrases,
  dropdown paraphrases, addresses, uncertainty, and corrections
- state/effect tests proving interpretation alone cannot confirm, skip, select,
  replace, or mutate a field
- multi-turn tests covering clarification, corrected answer, proposal,
  rejection, replacement, confirmation, remembered later answer, and return
  to a field
- before/after execution of the identical paraphrase suite with saved reports
  and a digest-checked comparison
- the complete established local regression gate

Automated implementation outcome recorded 19 October 2026:
- the fixed suite contains 19 synthetic scenarios and 40 scheduled turns across
  names, dates, number words, checkboxes, dropdowns, uncertainty, explanation,
  skip, return navigation, correction, bundled facts, and interruption
- its digest is `13246da029a1a841`; the pre-change revision `cc61298` and the
  candidate were run through the same configured
  `nvidia/Nemotron-3_5-Lightning` model using that identical digest
- pre-change deterministic failures were 34, form-state accuracy was 89.5%,
  latest-answer adherence was 28.6%, context retention was 50%, and recovery
  success was 0%
- the candidate recorded zero deterministic failures, 100% form-state
  accuracy, 100% latest-answer adherence, 100% context retention, and 100%
  recovery success; the comparison reported 34 fixed failures and no new or
  unchanged failures
- both runs retained zero invention, contradiction, repetition, and
  confirmation-boundary failures
- average turn latency increased from 142.886 ms to 340.122 ms on this focused
  model-handled suite; exact deterministic fast paths still make no interpreter
  call
- parser and orchestration coverage verifies strict schema fields, every
  intent, malformed and extra data, unknown and duplicate fields, excessive
  candidates, grounded evidence, prompt-injection-shaped text, provider
  failure, field adapters, multi-field memory, replacement preservation,
  support-preference grounding, navigation, and the confirmation boundary
- all 420 backend tests pass and the frontend production build succeeds; the
  existing Vite large-chunk warning remains non-blocking
- no frontend, PDF, voice-provider, Tavily, persistence, authentication, or
  deployment behavior changed
- manual sample/household completion and typed-versus-voice effect comparison
  remain pending, so this milestone is not marked complete

Clarification-routing refinement recorded 25 October 2026:
- manual sample-form QA exposed ordinary follow-up questions such as `what if
  they live there but they don't share cost` and `I don't know what this mean`
  being validated as numeric or date answers instead of reaching the existing
  field-explanation path
- the initial clarification regression suite contains 22 scenarios and 47
  turns with digest
  `8ca707a1061ca5a0`; it also proves that a second ordinary `yes` message cannot
  confirm a pending checkbox proposal
- on the configured `nvidia/Nemotron-3_5-Lightning` model, the pre-fix run had
  four deterministic failures and 50% context retention; the candidate had
  zero deterministic failures, 100% context retention, 100% form-state
  accuracy, zero invention failures, and zero confirmation-boundary failures
- common conditional clarification phrases use deterministic intent routing;
  a settled semantic `ask_explanation` interpretation is only an internal
  routing hint into the existing grounded explanation generator and is never a
  field value, public effect, or state transition
- follow-up browser QA exposed the shorter phrase `what do you mean` taking the
  answer-validation path for both a name and date field; that phrase and `what
  do you mean by this` now use the same deterministic explanation route
- the expanded live suite contains 23 scenarios and 49 turns with digest
  `82657b2869acabd7`; it passes with 100% form-state accuracy and context
  retention, zero deterministic failures, zero invention failures, and zero
  confirmation-boundary failures
- all 426 backend tests, both established offline Form Agent evaluations, all
  five frontend workflow checks, and the frontend production build pass; the
  existing Vite large-chunk warning remains non-blocking
- browser QA of the reported clarification flow remains pending, so the
  milestone status remains `IMPLEMENTED — MANUAL QA PENDING`

Required live/manual testing:
1. Run the fixed paraphrase suite through the configured Nemotron model before
   and after implementation and save both reports.
2. Complete the sample and household-support fixtures with synthetic facts
   while deliberately avoiding the field labels' exact wording.
3. Include one natural checkbox answer, one ordinary-language dropdown answer,
   one spoken-style date, one correction, one uncertain answer, and one message
   containing two facts.
4. Verify every accepted fact appears as a proposal before it can reach the PDF
   and that rejecting it leaves canonical state unchanged.
5. Repeat representative turns through typing and the existing voice adapter;
   identical transcripts must produce identical effects.

Do not implement:
- Deepgram or another speech provider; that remains Milestone 9.2
- a second agent, second model, agent framework, autonomous planning, model
  debate, model-selected tools, or model-authored state transitions
- silent confirmation, inferred personal facts, speculative spelling repair,
  eligibility decisions, or legal, financial, or medical advice
- frontend redesign, PDF extraction/filling changes, authentication,
  persistence, analytics, a database, deployment, or later milestone work

# Milestone 9.1.2 — Semantic-first conversational routing

Status: COMPLETE

Why this is next:
Milestone 9.1.1 added bounded semantic interpretation, but deterministic phrase
classification can still decide the conversational route before Nemotron sees
the turn. That makes ordinary questions and side comments dependent on an
ever-growing phrase list. The model should decide whether an ordinary message
is an answer, explanation request, uncertainty, correction, preference,
navigation request, or conversation; deterministic code should decide only
whether any resulting value or effect is safe.

Goal:
Make bounded Nemotron interpretation the first semantic decision for ordinary
typed or finalized-transcript messages while retaining deterministic field
validation, grounding, explicit confirmation, state transitions, guidance
policy, and PDF writing.

Target flow:

```text
ordinary user message
    -> bounded Nemotron intent and candidate interpretation
    -> non-factual intent routes to the existing grounded response path
    -> factual candidate passes deterministic grounding and field adapter
    -> visible proposal
    -> explicit confirmation
    -> canonical state and existing PDF fill path
```

Scope:
- semantically interpret ordinary messages while the interview is awaiting an
  answer, clarification, or replacement
- retain deterministic handling for explicit non-message events, pending
  proposal review, exact progress commands, reviewed-guidance policy, and
  already-closed setup effects
- retain the deterministic fast path for an unmistakable adapter-valid field
  value; conversational framing, ambiguity, or a non-proposal result invokes
  semantic interpretation
- treat the active field as the implicit referent for phrases such as `what do
  you mean`, `what are they getting at`, and `I am not sure what they want`
- route `ask_explanation` to the existing grounded explanation generator even
  when the interpreter is cautious about confidence; this route has no form
  effect and cannot create a candidate
- route unrelated comments and pauses to the existing natural-conversation
  response path rather than converting them into field-format errors
- route semantic uncertainty to a natural clarification response while still
  preventing a proposal
- keep interpreted answer candidates behind deterministic evidence grounding,
  field adapters, normalization, proposal review, and explicit confirmation
- use deterministic classification only as a safe provider-failure fallback,
  not the primary authority over ordinary conversation
- keep one Form Agent and the existing Nemotron Service; do not add another
  agent, framework, provider, or model debate

Acceptance criteria:
- an ordinary side comment cannot become a field proposal or field-format
  clarification and leaves the active question ready for an answer
- natural explanation requests reach the grounded explanation path without a
  phrase-specific production rule being required
- semantic uncertainty produces a focused non-mutating clarification and
  cannot become a proposal
- valid interpreted answers still pass through field-specific adapters and
  remain unconfirmed until a separate confirmation event
- malformed or unavailable interpretation leaves canonical state unchanged
  and uses the existing safe fallback
- progress, guidance, support-setup, confirmation, rejection, skip-button,
  direct-edit, and PDF behavior do not regress
- a fixed before/after suite shows fewer routing or context failures with no
  new invention, invalid-action, or confirmation-boundary failures
- the complete backend, evaluation, frontend, and build gates pass

Required testing:
- unit tests for explanation, uncertainty, unrelated conversation, factual
  answer, malformed interpretation, and provider-failure routing
- state/effect tests proving non-factual interpretations cannot mutate fields
- transcript scenarios for a pause/side comment and a natural explanation
  request that contains uncertainty language
- live before/after execution using an identical suite digest and model
- the complete established regression gate

Do not implement:
- Deepgram, voice-provider changes, audio handling, or name-confidence policy;
  those remain Milestone 9.2
- silent confirmation, model-authored state transitions, inferred personal
  facts, speculative spelling correction, or bypasses around field adapters
- frontend redesign, PDF changes, Tavily policy changes, persistence,
  authentication, deployment, or later milestone work

Automated implementation outcome recorded 25 October 2026:
- The live suite exercised 25 scenarios and 53 turns with suite digest
  `8681c11101715f7c` against `nvidia/Nemotron-3_5-Lightning`.
- A digest- and model-matched A/B run with semantic interpretation disabled
  recorded 35 deterministic failures, 0.920 form-state accuracy, 0.714 context
  retention, 0.400 latest-answer adherence, and 0.000 interruption recovery.
- With semantic-first routing enabled, the same suite recorded zero
  deterministic failures and 1.000 for form-state accuracy, context retention,
  latest-answer adherence, and interruption recovery.
- Both runs recorded zero invention, confirmation-boundary, and contradiction
  failures. Average measured turn latency increased from 137.318 ms to
  292.885 ms, a 155.567 ms cost accepted for the routing improvement.
- Provider responses that unnecessarily populate `referenced_field_id` for a
  non-navigation intent are now normalized to the closed non-operational slot;
  candidate grounding and actual return-to-field references remain strict.
- The complete backend suite passes with 429 tests. The focused semantic tests,
  deterministic evaluation, transcript evaluation, frontend workflow/layout/
  voice/reliability/support-preference checks, and production frontend build
  also pass.
- No frontend workflow, PDF, voice-provider, Tavily, persistence, or later-
  milestone functionality was changed.

Completion disposition recorded 29 October 2026:
- The user elected to accept the passing automated A/B, regression, evaluation,
  frontend, and build evidence and mark this milestone complete for now.
- No additional browser or voice manual-QA result is claimed. The following
  checks remain useful regression probes during normal testing of later work:
  - In the browser, try natural explanation requests such as `what do you mean`
    and `I am not sure what they want from me here` on text, date, and dropdown
    fields, and verify the assistant explains instead of issuing a format error.
  - Say or type a side comment such as `I need a moment to find the right
    document`; verify no proposal is created and the current question remains
    ready for an answer.
  - Give one natural valid answer and verify it still becomes a reviewable
    proposal that requires explicit confirmation before updating the form.
  - Repeat the explanation and pause checks through finalized voice transcripts
    to verify the shared typed/voice turn path in the browser.

# Milestone 9.2 — Deepgram streaming speech and identity-field handling

Status: IMPLEMENTED — LIVE VOICE DATASET AND MANUAL QA PENDING

Why this is next:
The current voice path relies on the browser's `SpeechRecognition` service,
requests one transcript alternative, and does not retain word confidence. That
is too opaque and inconsistent for important form facts, especially unfamiliar
names. Prompt changes cannot recover a name that speech recognition has already
misheard. Formless needs a controllable transcription boundary and a deliberate
recovery path for identity fields before the voice experience is frozen.

Goal:
Make Deepgram Nova-3 streaming the primary speech-to-text path and handle names
as high-risk identity values that can be repeated, spelled, corrected, reviewed,
and explicitly confirmed without the assistant guessing.

Technology and scope:
- use Deepgram Nova-3 through the streaming `/v1/listen` WebSocket API for
  speech-to-text only
- keep NVIDIA Nemotron through Nebius as the only conversational model; do not
  use Deepgram's Voice Agent, LLM, or text-to-speech products
- keep browser speech synthesis for assistant output during this milestone
- add a small speech-recognition adapter so provider transport, transcript
  events, and confidence metadata remain separate from the Form Agent
- keep the long-lived `DEEPGRAM_API_KEY` in the backend only
- let the backend request a short-lived Deepgram token when an explicitly
  started voice session needs a connection; connect the browser directly to
  Deepgram with that temporary token to avoid proxying live audio through the
  Form Agent or PDF Service
- use native browser microphone and WebSocket capabilities unless a focused
  dependency is demonstrably required
- expose interim text as `What I hear`, but send only one finalized utterance
  through the existing Form Agent message event
- retain final word confidence and timing only for the active turn so critical
  values can trigger a focused clarification
- configure endpointing for natural pauses and preserve the existing explicit
  start, stop, cancel, barge-in, and typed-fallback controls
- configure one English locale for this milestone; multilingual assistance and
  automatic language detection remain outside this scope
- use only bounded, non-personal form terminology as recognition keyterms;
  never send a guessed name or other invented personal fact as a keyterm
- do not persist audio, temporary tokens, confidence metadata, or transcripts;
  verify and document the provider's model-improvement/data-handling setting
  before the hosted demo

Name-specific interview policy:
- recognise name fields through the existing field-type/semantic adapter rather
  than asking Nemotron to decide whether a value is a name
- ask for the name exactly as it appears on the relevant official record
- when the PDF has separate name components, ask for the active component; when
  it has one full-name field, do not invent a different field split
- preserve what the recognizer heard and the user's original capitalization as
  reviewable input
- when confidence for a critical name token is below an evaluation-derived
  threshold, identify the uncertain part and ask the user to repeat or spell it
  instead of repeating the whole field question
- understand explicit spelling such as `A-K-H-O-O-N`, join the letters
  deterministically, and show the reconstructed value before confirmation
- support corrections such as `No, my surname is ...` without discarding a
  previously confirmed value until its replacement is explicitly confirmed
- apply only safe presentation capitalization; never use Nemotron, a
  dictionary, or recognition keyterms to guess or silently correct a person's
  name
- read the prepared name back and require the existing explicit confirmation
  effect before changing canonical form state

Architecture boundaries:
- voice remains an input/output adapter over the existing typed interview; it
  does not become a second agent or own form state
- Deepgram returns transcript evidence only and cannot select a field, create a
  proposal, confirm a value, call the PDF Service, or write PDF bytes
- the existing Form Agent remains responsible for conversation policy,
  field-aware interpretation, typed effects, and explicit confirmation
- transcript confidence is a recovery signal, not factual authority; high
  confidence does not bypass proposal review
- the browser recognizer is no longer the production or demo default after the
  cutover; any temporary development fallback must be explicit and must not
  activate silently
- if Deepgram is unconfigured or unavailable, retain the uploaded PDF,
  conversation, and confirmed values and offer the existing typed path

Acceptance criteria:
- an explicitly started voice session obtains a short-lived credential without
  exposing the long-lived Deepgram key to frontend source, network responses,
  logs, or the production bundle
- the primary voice path works in a supported browser even when
  `window.SpeechRecognition` is unavailable
- interim Nova-3 text is visibly distinguished from a final utterance
- each finalized utterance is dispatched to the existing Form Agent exactly
  once, with no partial transcript treated as an answer
- endpointing tolerates a natural mid-sentence pause without prematurely
  submitting the answer and finishes within a measured, documented latency
- cancelling or stopping a session closes microphone and WebSocket resources
  and has no form effect
- an ordinary high-confidence name becomes an unconfirmed proposal and is read
  back for explicit confirmation
- a low-confidence name token produces a targeted repeat-or-spell clarification
  and does not create a guessed proposal
- spoken letter-by-letter spelling and a subsequent component correction create
  the expected reviewable name while preserving the raw spoken answer
- name capitalization never changes letters or silently repairs spelling
- dates, numbers, finite choices, navigation commands, interruptions, and
  ordinary free text still use the existing validated Form Agent path
- Deepgram failure or missing configuration gives a clear recoverable message
  and leaves typing, direct PDF editing, the manual drawer, and canonical state
  usable
- no audio or speech metadata is stored after the active browser session
- existing PDF, Form Agent, confirmation, safety, and voice-interruption checks
  remain green

Required automated testing after implementation:
- backend configuration and short-lived-token tests with mocked Deepgram HTTP
  responses, including missing key, timeout, malformed response, and provider
  rejection
- security tests proving the long-lived API key is absent from API responses,
  frontend assets, exception text, and logs
- frontend parser tests for connected, interim, final, speech-final, confidence,
  empty, malformed, duplicate, close, and error WebSocket events
- lifecycle tests for microphone permission denial, explicit start, stop,
  cancel, reconnect, component unmount, and release of every media track/socket
- dispatch tests proving multiple interim revisions lead to exactly one final
  Form Agent message
- endpointing and barge-in regression tests, including assistant playback
  leakage, a real interruption, and a speaker who pauses mid-answer
- deterministic name-adapter tests for ordinary, unfamiliar, hyphenated,
  apostrophised, multi-part, letter-spelled, corrected, and low-confidence names
- tests proving no uncertain or corrected name reaches canonical field state
  before its matching explicit confirmation
- provider-unavailable tests proving typed completion retains the current PDF,
  transcript, pending proposal, and confirmed values
- the complete established local regression gate

Required live and manual testing after implementation:
1. Create a synthetic voice set covering at least 20 short utterances across
   names, dates, postcodes, reference numbers, yes/no answers, and commands.
2. Run the same set through the current browser recognizer before cutover and
   Nova-3 after integration; record exact critical-entity accuracy, duplicate or
   dropped submissions, clarification rate, and final-transcript latency.
3. Include unfamiliar, hyphenated, apostrophised, and multi-part synthetic names
   spoken normally and then spelled after one deliberate misrecognition.
4. Complete the sample and household-support fixtures by voice using synthetic
   facts, including one name correction, one interruption, and one typed fallback.
5. Deny microphone permission, unset the Deepgram key, interrupt the network,
   and verify that the form remains recoverable through typing and manual edit.
6. Inspect browser network traffic, backend logs, and the production bundle to
   confirm that only a short-lived token reaches the browser and no audio is
   retained by Formless.

Completion evidence to record:
- selected Nova-3 model and English locale
- focused automated-test commands and full regression output
- before/after critical-entity accuracy and latency table using the fixed
  synthetic voice set
- a short transcript showing low-confidence surname clarification, spelling,
  proposal review, correction, and confirmation
- browser and operating-system versions used for the live voice test
- provider data-handling/model-improvement configuration and any remaining
  privacy limitation
- known speech limitations and the demonstrated typed fallback

Do not implement:
- Deepgram Voice Agent, Flux, Deepgram text-to-speech, a second conversational
  model, a second agent, or autonomous voice-owned form actions
- multilingual assistance, language auto-detection, translation, speaker
  identification, diarisation, telephony, call recording, or persistent audio
- silent model correction of names or any other personal fact
- authentication, accounts, databases, analytics, or transcript persistence
- PDF extraction or filling changes unrelated to preserving the existing safe
  voice-to-confirmation path
- deployment, submission, or later milestone work

Automated implementation outcome recorded 29 October 2026:
- The primary input adapter now uses Deepgram Nova-3 on `/v1/listen` with the
  fixed `en-GB` locale. It requests a backend-issued temporary bearer token;
  the long-lived API key remains server-side.
- Native browser `MediaRecorder` and WebSocket APIs stream one microphone turn
  directly to Deepgram. No Deepgram SDK, Voice Agent, LLM, or TTS dependency
  was added, and `window.SpeechRecognition` is no longer required or used.
- Interim text is visibly labelled, finalized segments are deduplicated and
  buffered, and only one complete utterance callback can reach the existing
  Form Agent turn path.
- Endpointing is configured at 700 ms with a 1,500 ms utterance-end window and
  an 850 ms client settle guard after `speech_final`. Automated pause tests
  prove continued speech cancels the pending completion; live latency remains
  to be measured.
- Word confidence and timing remain in active frontend memory only. The
  provisional name threshold is 0.82: a lower-confidence token produces a
  targeted repeat-or-spell message and no Form Agent message. The threshold
  must be confirmed or adjusted from the required synthetic live voice set.
- The deterministic name adapter joins explicit runs such as `A-K-H-O-O-N`
  while preserving the raw recognized form for review. Hyphens, apostrophes,
  multiple name components, capitalization, and letter order are otherwise
  preserved; every accepted name still becomes an unconfirmed proposal.
- Recognition keyterms are limited to a small non-personal allowlist. Every
  Deepgram streaming URL sets `mip_opt_out=true`; Formless stores no audio,
  temporary token, transcript confidence, or timing metadata after the active
  browser turn.
- Mocked backend tests cover configuration, temporary tokens, timeout,
  malformed responses, provider rejection, missing configuration, secret
  redaction, and the public API response. Frontend tests cover parsing,
  interim/final/duplicate/empty/malformed/error events, exactly-once dispatch,
  endpointing, permission denial, retry, stop, cancel, socket failure, and
  release of media and WebSocket resources.
- The complete backend suite passes with 449 tests. All established frontend
  workflow, layout, interruption, reliability, support-preference, and new
  Deepgram checks pass, and the production frontend build succeeds.

Live blocker and remaining completion evidence:
- The original project-level key returned HTTP 403 from `/v1/auth/grant`; it
  has since been replaced by a Member-level key and the temporary-token and
  synthetic streaming connection checks pass.
- No live critical-entity accuracy, duplicate/drop rate, clarification rate,
  final-transcript latency, browser/OS matrix, or complete fixture transcript
  is claimed yet. The required live/manual steps above remain open, so this
  milestone is not complete.

# Milestone 9.2.1 — Nemotron-first conversational orchestration

Status: IMPLEMENTED — LIVE EVALUATION COMPLETE; BROWSER QA PENDING

Why this is next:
Milestone 9.1.2 made semantic interpretation the first route for many
conversational turns, but the implementation still calculated deterministic
policy first, bypassed Nemotron for exact-looking answers, and then required a
second regex/adapter interpretation to independently agree with Nemotron's
meaning. That made ordinary phrases such as `make things clearer`, `either is
fine`, or a natural dropdown answer depend on several overlapping gates. It
also caused the assistant to discard values it had correctly understood.

Goal:
Let the existing Nemotron model own the meaning and conversational reply for
every eligible natural message, while deterministic code owns field IDs,
allowed value shapes and options, legal state transitions, explicit
confirmation, canonical form state, and PDF effects.

Target flow:

```text
natural typed or finalized voice message
    -> one bounded Nemotron turn decision
       (intent, natural reply, candidates, uncertainty, source evidence)
    -> structural field/type/option and state validation
    -> focused clarification, non-mutating reply, or visible proposal
    -> separate explicit confirmation
    -> canonical state and existing PDF fill path
```

Scope:
- send natural messages in support setup, awaiting answer, awaiting
  clarification, and awaiting replacement to Nemotron before deterministic
  semantic policy
- extend the bounded decision with a concise natural `assistant_reply`, closed
  guidance/progress/start intents, and the closed `no_preference` interaction
  mode
- include the active field, bounded recent history, setup step, assistance
  preferences, real field IDs, field types, and finite options in the bounded
  prompt
- let Nemotron remove conversational framing and return an unambiguous value
  in the field's requested representation, including dates, spoken numbers,
  checkboxes, finite options, capitalization, and deliberately spelled words
- require exact latest-turn evidence for every personal-fact candidate and
  reject unknown fields, invalid field types, and values outside finite options
- do not pass an accepted semantic candidate through a second general-purpose
  regex or adapter meaning check; field preparation may still apply visible,
  conservative presentation formatting
- accept a medium-confidence interpretation when the model says no
  clarification is needed; `needs_clarification` remains the explicit boundary
  for ambiguous, incomplete, contradictory, or uncertain facts
- use the model's bounded natural reply for proposals, focused clarification,
  and side conversation; reject proposal wording that falsely claims an
  unconfirmed value was already saved, applied, or confirmed
- keep explicit UI events, proposal confirmation/rejection, confirm-edit,
  skip-button events, canonical state transitions, guidance lookup, and PDF
  filling deterministic and closed
- retain the established deterministic interpretation path only as a provider
  failure/invalid-response fallback and as an explicit test seam for adapters
  and state-machine policy

Acceptance criteria:
- an exact-looking answer and a paraphrased answer both reach Nemotron before
  any semantic answer policy
- a natural dropdown or checkbox meaning accepted by Nemotron is not rejected
  merely because a regex cannot reproduce the interpretation
- unknown field IDs, non-boolean checkbox values, invalid number values, and
  values outside supplied dropdown options cannot become proposals
- a candidate must cite an exact contiguous excerpt from the latest user turn;
  bounded history cannot silently supply a missing current personal fact
- ambiguous or incomplete answers produce one focused clarification and no
  field effect
- side conversation produces one natural non-mutating response rather than a
  second model-action round trip or a field-format error
- proposals remain review-only, cannot claim they were already applied, and
  require the existing separate confirmation event before canonical state or
  PDF output changes
- provider failure uses the conservative established fallback without
  mutating the original request
- deterministic adapter/state tests, semantic integration tests, complete
  backend/evaluation gates, frontend regression checks, and production build
  pass

Required live/manual testing:
1. Run the fixed paraphrase-heavy and human-helper suites using the configured
   Nemotron model and save the report and suite digest.
2. Complete the sample and household-support fixtures with natural phrasing,
   including `make things clearer`, `either is fine`, one ordinary-language
   dropdown answer, one checkbox answer, one spoken date, one uncertain answer,
   one correction, and one message containing two facts.
3. Repeat the clarification probes `what do you mean`, `what if they live there
   but do not share costs`, and `I do not know what this means`; verify they are
   not treated as attempted field values.
4. Repeat representative turns through Deepgram final transcripts, including a
   deliberately spelled name, and verify the same bounded decision and proposal
   boundary as typed input.
5. Confirm that rejected proposals, provider failure, and invalid model output
   leave canonical form state and the source PDF unchanged.

Do not implement:
- direct model writes to fields or PDFs, silent confirmation, inferred personal
  facts, speculative missing letters/date components, or model-selected tools
- another agent, agent framework, model debate, second conversational model,
  Deepgram Voice Agent, or another speech provider
- frontend redesign, PDF extraction/filling changes, multilingual assistance,
  persistence, authentication, analytics, deployment, or later milestones

Automated implementation outcome recorded 29 October 2026:
- eligible natural setup, answer, clarification, and replacement messages now
  reach the bounded Nemotron turn decision before deterministic semantic policy
- the decision now includes closed guidance, progress, and setup-start intents,
  `no_preference`, bounded assistance context, and an optional natural reply
- interpreted candidates retain exact latest-turn evidence and are checked
  against real field IDs, structural field types, finite options, active phase,
  and closed proposal effects without a second general semantic-adapter vote
- model replies can make proposals and clarification more conversational, but a
  false claim that an unconfirmed value was saved, applied, or confirmed is
  replaced by safe review wording
- explicit confirmation, rejection, edited confirmation, navigation effects,
  canonical state, Tavily policy, and PDF extraction/filling remain unchanged
- 456 backend tests pass; the 14-scenario evaluation and five-fixture, 47-turn
  transcript evaluation report zero failures, invalid actions, invalid
  proposals, invention failures, and confirmation-boundary failures
- all six frontend workflow, layout, interruption, reliability, Deepgram, and
  support-preference checks pass, and the production frontend build succeeds
  with only the existing non-blocking Vite chunk-size advisory
- the required configured-model and browser/Deepgram manual runs above have not
  yet been recorded, so this milestone is implemented but not marked complete

# Milestone 9.2.2 — Context-rich Nemotron conversation and natural review

Status: IMPLEMENTED — LIVE/MANUAL QA PENDING

Problem to solve:
The assistant now asks Nemotron to interpret eligible natural messages, but a
real session can still alternate between model-written replies and older
deterministic templates. The model does not consistently receive the complete
active-question and pending-review context it needs, pending proposal decisions
remain unusually rigid, and conservative fallback behavior can look like a
form validator rather than a person helping beside the user. This is visible in
repeated field headings, `You said ... I prepared ...` narration, explanation
requests that initially repeat the question, noisy name proposals, dates
accepted in the wrong displayed format, and dropdown guesses that invent facts.

Goal:
Make one bounded Nemotron decision the conversational authority for every
natural turn in the guided interview, including proposal review, while keeping
all state-changing effects closed, structurally validated, and explicitly
confirmed. Give Nemotron enough real form context to understand the user's
meaning and respond naturally; use deterministic code to enforce what may
change, not to script how the assistant speaks.

Target turn flow:

```text
latest typed or finalized voice message
        +
active question, field constraints, finite options, pending review,
canonical progress, relevant form map, assistance preferences, recent history
        |
        v
one bounded Nemotron conversational decision
        |
        +-- natural assistant reply
        +-- closed intent and exact user evidence
        +-- optional candidate values tied to real field IDs
        +-- explicit ambiguity / clarification reason
        |
        v
deterministic structural and state validation
        |
        +-- no effect / focused clarification / reviewable proposal
        +-- explicit review decision only when the latest words clearly say so
        |
        v
canonical state changes only through an allowed closed effect
```

Context supplied to Nemotron:
- the latest user message as the authoritative turn evidence
- the current conversation phase and current support-setup step
- the active field's stable ID, real question, user-facing label, plain-language
  help text when available, section, page, and field type
- every actual finite option for dropdown, radio, or checkbox fields, including
  the distinction between display text and stored AcroForm value
- deterministic field constraints such as required date representation,
  numeric shape, multiline capability, and unsupported/placeholder values
- the currently pending proposal or replacement, its original and prepared
  values, and the previous confirmed value when a correction is in progress
- canonical confirmed, skipped, proposed, and unanswered counts, plus only the
  minimum referenced canonical value needed for a correction or review answer
- a compact ordered map of supported questions so volunteered facts,
  navigation, and references such as `the address question` remain grounded
- bounded recent conversation history, with the active unresolved exchange
  retained explicitly even if it falls outside the ordinary history window
- the user's explicit session-only assistance preferences and current
  interaction mode
- reviewed-guidance availability and source metadata only when the existing
  guidance policy has selected it

Context boundaries:
- do not send raw PDF bytes, rendered pages, audio, temporary speech tokens,
  hidden unsupported fields, or every confirmed personal answer
- do not rely on model memory outside the supplied request
- treat form text, history, assistance notes, user text, and external guidance
  as bounded untrusted data
- keep the prompt within explicit field, option, history, candidate, and
  character limits and test those limits

Nemotron decision contract:
- distinguish answer, several supplied answers, correction, explanation,
  simpler explanation, uncertainty, side question, frustration, pause,
  assistance-preference change, progress/review, navigation, skip, start,
  proposal confirmation, proposal rejection, proposal edit, repeat/read-back,
  and unrelated conversation
- return a concise natural reply separately from any candidate or requested
  workflow operation
- cite an exact excerpt from the latest message for every proposed personal
  fact and every review decision
- reference only real supplied field IDs and exact finite values from the
  supplied schema
- report what is ambiguous or missing instead of filling the gap with a likely
  answer
- never return a frontend effect, call Tavily, write canonical state, confirm a
  value itself, or call the PDF Service

Conversational behavior:
- answer the latest message first, then return to the form only when useful
- vary sentence structure naturally; do not require `You said`, `I prepared`,
  `Please review and confirm`, or a repeated workflow menu
- let the active-question card carry the formal field heading instead of
  repeating it at the start of every assistant message
- make a proposal sound like normal spoken review, for example `Got it — John
  Michael. Is that exactly how it appears on your official documents?`
- after confirmation, acknowledge briefly and ask the next real question, for
  example `Thanks. And what would you like me to call you?`
- adapt detail, pace, and vocabulary from the explicit assistance preferences
  and recent repair attempts without diagnosing the user
- if the user asks again, materially simplify or explain a different part
  rather than repeating substantially the same sentence
- preserve the user's uncertainty and never become more precise than the user
  was
- keep proposal details and transformations in the separate review card even
  when the spoken reply is concise

Finite-choice and constrained-field behavior:
- give Nemotron the complete available option list and ask it to distinguish
  an answer that selects an option from information that is merely related
- map an ordinary paraphrase to an exact option only when the user's words
  establish that option without an unsupported assumption
- when the answer establishes only part of the distinction, ask one focused
  question that explains what still matters
- `I live by myself` must not become `Living with family or friends`, `Sole
  tenant`, or `Owner-occupier`; it should lead to a tenure-focused follow-up
- `Solo tenant` may become a reviewable `Sole tenant` candidate because the
  supplied option and user evidence establish one unambiguous match
- an input such as `05/19/2011` for a field explicitly requiring `DD/MM/YYYY`
  must be clarified rather than stored in an incompatible or guessed format
- checkbox answers may map natural agreement or disagreement to the supplied
  boolean state, but remain pending until explicit review confirmation

Name and identity behavior:
- treat duplicated words, mixed normal speech and letter spelling, and
  conflicting name variants as uncertainty rather than combining everything
  into a malformed proposal
- when one component is uncertain, ask for only that component to be repeated
  or spelled
- preserve the exact letters supplied; capitalization may be prepared visibly,
  but Nemotron must not silently repair an unfamiliar name
- let Deepgram confidence remain supporting turn evidence, not authority to
  guess, reject, or confirm an identity value
- keep every name proposal and correction behind the existing visible review
  and explicit-confirmation boundary

Natural proposal-review behavior:
- include pending proposal context in the model decision so a spoken or typed
  review response is interpreted against the exact value visibly awaiting
  review
- clear phrases such as `yes, that is correct`, `confirm that`, `no, reject
  it`, `say it again`, or `change the surname to ...` may request an existing
  closed review event
- deterministic validation must verify the phase, pending field, pending
  value, exact latest-turn evidence, and allowed decision before returning the
  corresponding effect
- vague acknowledgements, unrelated answers, low-confidence transcripts, and
  near-matches such as a recognition result of `permit` must not confirm a
  proposal; the assistant should ask a short review-specific clarification
- a correction creates a new reviewable replacement and never overwrites the
  current confirmed value before separate confirmation
- duplicate or stale confirmations remain no-ops with a natural recovery
  response

Fallback and observability:
- record privacy-safe development diagnostics showing whether a turn used the
  primary Nemotron decision, a corrected model response, or provider fallback
- diagnostics may include phase, intent category, validation reason, latency,
  and fallback category, but must not log user text, field values, PDF content,
  API keys, or personal answers
- provider or parsing failure may use a grounded fallback, but it should ask a
  useful question and must not silently switch to a misleading proposal
- tests must be able to assert the selected route so old deterministic wording
  cannot appear unpredictably without a visible failure reason
- manual completion and direct PDF editing remain available when Nemotron is
  unavailable

Acceptance criteria:
- every eligible natural turn in support setup, answering, clarification,
  replacement, and proposal review receives the bounded Nemotron decision
  before conversational wording is chosen
- Nemotron receives the complete active-field constraints and every valid
  finite option, plus bounded form, state, preference, pending-review, and
  history context
- deterministic code validates provenance, IDs, types, options, phases, and
  effects without requiring a second general-purpose semantic interpretation
- the assistant's normal reply is natural and does not have a required canned
  opening, closing, field heading, or confirmation paragraph
- explanation requests are answered on the first attempt and remain anchored
  to the current question
- repeated explanation requests produce materially simpler or differently
  focused help
- insufficient information about a dropdown distinction produces a focused
  follow-up and never an invented option or invented factual rationale
- incompatible or ambiguous dates, names, numbers, and identifiers produce a
  targeted clarification rather than an invalid proposal
- clear natural proposal decisions use the existing closed effects; vague or
  misrecognized review speech cannot confirm or reject anything
- proposals and replacements remain visibly pending, and canonical values and
  PDF bytes change only after an allowed explicit confirmation effect
- route diagnostics identify semantic fallback without retaining user content
  or credentials
- provider failure, malformed output, and correction failure leave the active
  field, pending proposal, canonical values, source PDF, and manual workflow
  intact
- the complete backend, evaluation, PDF, frontend, voice, safety, and
  human-helper regression gates pass

Required automated testing:
- prompt/context tests for active question, help text, field constraints,
  finite options, pending proposal, relevant history, assistance preferences,
  compact form map, and all configured context bounds
- parser tests for every closed intent, exact evidence, candidate type,
  clarification reason, review decision, malformed JSON, extra keys, unknown
  fields, invalid options, prompt injection, and false saved/confirmed claims
- state/effect tests for natural confirmation, rejection, edit, repeat, skip,
  stale review, duplicate review, ambiguous acknowledgement, and near-match
  speech with no unintended mutation
- transcript tests based on the observed sessions, including repeated/spelled
  names, first-attempt `What does that mean?`, progressively simpler wording,
  `05/19/2011` in a `DD/MM/YYYY` field, `I live by myself`, `Solo tenant`, and
  a proposal followed by `Permit`
- explicit safety assertions that `I live by myself` never maps to `Living
  with family or friends` and never invents lease, ownership, household, or
  co-tenant facts
- diagnostics tests proving fallback metadata excludes user text, candidate
  values, PDF content, and secrets
- a fixed before/after live Nemotron comparison using the same suite digest
- the complete established local regression gate

Required live/manual testing:
1. Restart the backend so the tested process contains this milestone's code.
2. Repeat both observed sample and household-support transcripts using
   synthetic values, once by typing and once through Deepgram final transcripts.
3. Ask for the same explanation at least three ways and verify each response
   addresses the latest wording without repeating a template.
4. Exercise one checkbox, dropdown, date, number, full-name, correction,
   pending-review confirmation, rejection, and ambiguous review utterance.
5. Temporarily make Nemotron unavailable and verify the diagnostic route,
   natural safe fallback, unchanged canonical state, and manual completion.
6. Inspect logs and browser/backend network data to verify no personal answer,
   PDF content, or credential was added to diagnostics.

Completion evidence to record:
- exact model ID, suite digest, scenario and turn counts, model-call count, and
  latency distribution
- before/after contextual relevance, first-turn explanation success,
  clarification success, dropdown inference safety, repeated-response rate,
  first-attempt proposal rate, and turns per confirmed field
- complete synthetic transcripts for the two observed failure flows
- privacy-safe fallback examples and provider-failure result
- full regression output and remaining conversational limitations

Do not implement:
- direct model-to-state or model-to-PDF writes, silent confirmation, invented
  personal facts, autonomous tools, or model-selected Tavily calls
- another agent, agent framework, model debate, or second conversational model
- unbounded history, server-side conversation persistence, analytics,
  authentication, a database, OCR, XFA, or new PDF-format support
- the continuous microphone lifecycle or fixed workspace planned for the next
  milestones

Automated implementation outcome (2026-10-29):
- eligible support-setup, answer, clarification, replacement, and pending-review
  messages now reach one bounded Nemotron turn decision before conversational
  wording is selected
- the turn context includes the full active question/help/type/page/section,
  all schema-bounded finite options, explicit field constraints, pending review,
  canonical progress, assistance preferences, eight bounded history messages,
  and an active-first forty-question map
- natural confirmation, rejection, edit, read-back, skip, and correction
  requests remain behind exact latest-message evidence, phase/pending-value
  validation, existing closed effects, and visible proposal review
- finalized Deepgram speech now follows the same message route instead of a
  frontend review phrase table; only the local pause command remains local
- focused constraints reject incompatible numeric date order, unsupported
  housing inference, and duplicated/conflicting mixed spoken-spelled names while
  allowing a clean deliberately spelled component and exact finite-option match
- privacy-safe route diagnostics expose only phase, bounded intent, and route
  category; provider failure keeps pending/canonical state unchanged
- the versioned synthetic live suite
  `evaluations/scenarios/context_rich_natural_review.json` contains eight fixed
  conversations and has digest `86848eab35b30a83`
- deterministic backend coverage passes for context bounds, every review
  operation, `permit`, dropdown inference, date order, name spelling, fallback,
  and diagnostics; the complete backend and frontend regression results are
  recorded in the implementation handoff
- the configured-model suite was rerun against
  `nvidia/Nemotron-3_5-Lightning` with the unchanged digest
  `86848eab35b30a83`: all 20 turns completed with exact form state, zero
  deterministic, invention, contradiction, confirmation-boundary, or
  qualitative failures, and the correctness gate passed
- compared with the original live baseline, deterministic failures fell from
  4 to 0, qualitative failures from 21 to 0, invention failures from 1 to 0,
  clarification quality rose from 3.75 to 4.25, and average turn latency fell
  from 496.209 ms to 480.977 ms; no new failures were introduced
- the comparison is recorded at
  `backend/evaluations/results/milestone-9-2-2-live-comparison.json`; the
  focused suite does not contain the explicit long-form human-helper behavior
  checks, so its separate human-helper gate is intentionally not evidence of
  browser-session completion
- the required typed plus Deepgram browser sessions above have not yet been
  recorded, so this milestone is not marked complete

# Milestone 9.2.3 — Continuous hands-free voice session

Status: IMPLEMENTED — LIVE/MANUAL QA PENDING

Problem to solve:
Deepgram now provides a controlled one-utterance transcript, and the existing
voice loop can speak, listen, and detect some interruptions. The experience
still exposes the underlying turn machinery: users may have to press `Answer
now`, retry listening after silence, or manually interrupt the helper. A person
helping beside the user would keep the conversation open, notice when the user
starts speaking, pause, listen, and continue without a button press on every
turn.

Goal:
After one deliberate `Start conversation` action, maintain one visible,
session-scoped hands-free interview until the user pauses, mutes, ends, changes
the PDF, or encounters a non-recoverable permission/provider failure. Reuse
Deepgram, browser speech synthesis, the existing Form Agent endpoint, and the
same canonical state; do not create a voice agent or voice-owned form path.

Session state model:
- `inactive`: no microphone access and no automatic speech
- `requesting_permission`: the explicit start is obtaining microphone access
- `listening`: the user may speak naturally and interim text is visible
- `finalizing`: the current utterance boundary is settling and deduplicating
- `thinking`: one finalized transcript is being processed by the Form Agent
- `speaking`: the already-visible assistant reply is being read aloud
- `interrupted`: real user speech stopped playback and is opening recognition
- `paused`: microphone and automatic turn-taking are stopped but state remains
- `recovering`: one bounded automatic provider/session recovery is in progress
- `ended`: resources are released; typing and manual editing remain available

Hands-free turn rhythm:
1. The user selects `Start conversation` once and grants microphone permission.
2. If an assistant response is waiting, it is spoken; otherwise the session
   begins listening.
3. After speech completes, listening opens automatically without another
   button press.
4. Interim Deepgram text is visible but never dispatched as a form answer.
5. A guarded pause finalizes exactly one utterance and sends it through the
   existing message/review-event path.
6. While the backend is thinking, the microphone cannot dispatch a second
   conflicting turn; any supported queued interruption remains bounded and
   visible.
7. The returned assistant reply becomes visible before it is spoken.
8. The loop resumes automatically until paused, muted, ended, or blocked.

Interruption and barge-in:
- while the assistant is speaking, keep a conservative local speech-activity
  path capable of distinguishing probable user speech from playback leakage
- sustained probable speech stops synthesis, acknowledges the interruption,
  and begins the same Deepgram utterance path without requiring `Answer now`
- a short noise, keyboard tap, cough, room sound, or the assistant's own voice
  must not interrupt the response
- if the user begins speaking during the final words, their utterance must not
  be lost while audio resources transfer from playback monitoring to Deepgram
- a manual `Interrupt` or `Answer now` control may remain as an accessibility
  fallback, but it must not be required for normal hands-free use
- spoken interruptions enter the same Nemotron decision and closed-effect
  validation as typed turns

Silence and recovery:
- ordinary silence is not an error and does not display `I didn't hear any
  speech` or require `Try listening again`
- remain ready to listen after a normal silent interval, or gently reprompt
  once after a documented longer interval without advancing the form
- an empty or duplicate final transcript creates no Form Agent request and no
  form effect
- recover one transient Deepgram disconnect or expired temporary token
  automatically when safe; repeated failure pauses the session with one clear
  typed fallback
- a low-confidence identity turn asks the targeted repeat-or-spell question and
  automatically listens again
- pause, mute, end, form replacement, permission revocation, provider failure,
  browser backgrounding policy, and component unmount release every stream,
  recorder, socket, audio node, timer, and speech callback

Privacy and user control:
- no microphone access occurs before explicit start or after pause/end
- keep `Listening`, `Thinking`, `Speaking`, `Paused`, and recovery state visible
  at all times without relying only on colour
- provide permanent `Mute`, `Pause`, and `End` controls plus the typed composer
- explain once that the microphone remains active only for the current visible
  session and that Formless does not store audio
- stream active-session audio directly to Deepgram with the existing temporary
  credential and `mip_opt_out=true`; do not proxy it through the Form Agent
- do not persist audio, confidence, interim text, token data, or timing after
  the active turn/session boundary already documented by the voice adapter

Acceptance criteria:
- one explicit start is sufficient to complete multiple consecutive questions,
  explanations, proposals, confirmations, corrections, and skips by voice
- listening resumes automatically after every spoken assistant turn and safe
  recoverable error without a retry button
- ordinary silence neither advances the form nor ends the session
- a real spoken interruption stops playback and captures exactly one utterance
  without losing the beginning or sending playback audio as the user's answer
- playback leakage and representative non-speech noises do not interrupt the
  assistant or dispatch a transcript
- only one finalized transcript or closed spoken review event reaches the Form
  Agent per utterance
- proposal confirmation still requires clear review language tied to the
  visible pending proposal; vague or low-confidence speech cannot confirm
- pause, mute, end, permission failure, provider failure, PDF replacement, and
  unmount leave canonical state unchanged and release all audio resources
- typing, proposal buttons, direct PDF editing, and the manual drawer remain
  usable throughout and share the same state
- no voice-specific agent, backend conversation endpoint, PDF path, state
  store, runtime dependency, or persistence system is introduced
- the complete voice, frontend, backend, conversation, safety, and PDF
  regression gates pass

Required automated testing:
- session-state transition tests covering start, permission, listen, finalize,
  think, speak, interrupt, resume, pause, mute, recover, end, reset, and unmount
- fake-timer tests proving silence does not create an error, duplicate request,
  automatic skip, or endless rapid reconnect loop
- exactly-once dispatch tests across interim revisions, multiple final events,
  pause/resume, barge-in, stale callbacks, reconnect, and rapid assistant turns
- acoustic-policy tests for calibrated playback, real speech, short spikes,
  steady noise, cough-like bursts, delayed resource transfer, and speech near
  the end of playback
- lifecycle tests proving all media tracks, recorders, sockets, audio contexts,
  detectors, speech synthesis, timers, and callbacks are released
- integration tests for voice answer, explanation, proposal, natural
  confirmation, ambiguous confirmation, correction, skip, and low-confidence
  name recovery through the existing typed Form Agent contract
- accessibility tests for visible state labels and keyboard-operable mute,
  pause, end, interrupt fallback, and typed input
- the complete established local regression gate

Required live/manual testing:
1. On the target demo laptop and browser, start once and complete at least ten
   consecutive turns without pressing a recording, interrupt, or retry button.
2. Interrupt the assistant early, in the middle, and during its last words;
   verify speech stops only for the user's actual voice and no words are lost.
3. Introduce representative room noise, typing, a cough, and speaker playback;
   verify none is treated as a user turn.
4. Remain silent through the configured interval, then answer normally without
   selecting retry.
5. Exercise pause/resume, mute/unmute, end/restart, denied permission, a
   disconnected network, and one expired/rejected temporary token.
6. Complete a sample-form voice path containing an explanation, uncertain name,
   spelled correction, checkbox, rejection, confirmation, and final review.
7. Inspect browser indicators and network traffic to confirm microphone access
   stops on pause/end and audio goes only to Deepgram during the visible session.

Completion evidence to record:
- browser, operating system, microphone/speaker arrangement, Deepgram model,
  locale, endpointing, silence, barge-in, and reconnect settings
- ten-turn uninterrupted transcript with synthetic information
- false-interruption rate, missed-interruption rate, duplicate/drop rate,
  silence recovery result, final-transcript latency, and end-to-reply latency
- lifecycle/resource-cleanup results and provider-failure fallback
- known acoustic limitations and the demonstrated typed/manual fallback

Do not implement:
- microphone access before explicit start, background listening after end,
  wake words, speaker identification, audio recording, stored transcripts,
  telephony, or call history
- Deepgram Voice Agent, Deepgram TTS, another speech provider, a second agent,
  or direct voice-to-PDF writes
- automatic confirmation from noise, vague acknowledgement, or model prose
- the fixed workspace or release work planned for later milestones

Automated implementation outcome (2026-10-29):
- one explicit start now maintains the frontend-owned session across assistant
  speech, bounded Deepgram turns, Form Agent thinking, proposals, and subsequent
  questions without another record or retry action
- silence produces no message or form effect and reopens listening with bounded
  exponential backoff; one transient Deepgram failure retries automatically,
  while repeated or non-recoverable failure pauses voice with typing intact
- low-confidence name speech speaks the targeted repeat-or-spell prompt and
  automatically listens again rather than requiring a retry button
- mute, pause, end, form replacement, page backgrounding, and unmount invalidate
  stale callbacks and release recognition, speech, interruption, timer, socket,
  recorder, audio-context, and microphone resources
- barge-in transfers the detector's already-open microphone stream into the
  same Deepgram recognizer, reducing the handoff gap without creating a second
  audio or conversation path
- active-turn capture now starts before the temporary-token and WebSocket
  handshake finishes; a bounded memory-only queue flushes those opening audio
  chunks in order once connected so immediate hands-free answers do not lose
  their first words
- direct recognition requests automatic gain control and mono input where the
  browser supports them, while the playback-leakage detector keeps its separate
  conservative capture settings; bounded finite dropdown options are supplied
  as schema-owned Nova-3 keyterms to improve recognition of valid choices
- explicit session transitions now cover inactive, active, muted, paused, and
  ended modes, with visible interruption and recovery states and permanent
  keyboard-operable Mute, Pause, End, Answer now, and typed fallbacks
- focused Deepgram, acoustic interruption, continuous-session, existing PDF,
  workspace, reliability, preference, and production-build checks pass; live
  ten-turn, opening-word accuracy, room-noise, interruption-timing, permission,
  and network evidence remains required before this milestone can be marked
  complete

# Milestone 9.2.4 — Fixed-viewport conversational workspace

Status: NOT STARTED

Problem to solve:
The loaded application contains all required controls, but users can still
scroll the whole page between microphone state, current question, transcript,
proposal review, composer, PDF position, and manual controls. That makes it
hard to know whether Formless is listening, what question is active, where a
proposal is waiting, or where to answer. The interface should behave like a
stable document-and-helper workspace rather than a long dashboard.

Goal:
Keep the loaded experience inside the usable browser viewport. Give the PDF and
assistant separate, predictable scrolling regions; keep voice/session state,
current question, proposal review, and input reachable without whole-page
scrolling; and preserve the existing single canonical state and accessibility
fallbacks.

Desktop layout:
- use one compact application header for product, filename, progress, change
  PDF, review, and download actions
- place the PDF stage on the left and the assistant workspace on the right in a
  stable approximately 58/42 split at representative laptop widths
- size the loaded workspace from the available viewport height after the app
  header; the document body itself should not become the primary scroll region
- let PDF pages and page controls scroll or navigate only inside the PDF stage
- let conversation history scroll only inside the assistant transcript region
- keep the two panes mounted so navigation, page, transcript, proposal, and
  canonical state are never recreated by layout changes

Assistant layout:
- pin one compact session bar at the top showing `Listening`, `Thinking`,
  `Speaking`, `Paused`, `Needs attention`, or `Complete`, plus Mute, Pause, and
  End when valid
- keep section, page, progress, and the active question immediately below the
  session bar rather than burying them in transcript history
- display the most recent exchange and current conversational context in one
  internally scrollable transcript, with the full transcript still accessible
- place a pending proposal/replacement review adjacent to the latest relevant
  exchange and ensure its confirmation controls cannot scroll out of reach
  while awaiting a decision
- pin the typed composer or context-valid review controls at the bottom of the
  assistant pane above browser safe-area insets
- show Deepgram interim text near the composer without duplicating it as a
  permanent user message before finalization
- keep guidance sources, provider details, full transcript controls,
  assistance adjustments, and `Edit all fields` behind clearly labelled
  secondary disclosures
- avoid repeating the active field as both a large card heading and the first
  line of every assistant bubble

Mobile and constrained layouts:
- retain the accessible `Assistant` / `Form` view switch and default to the
  assistant during an active conversation
- make the selected view use the available viewport height with its own
  internal scroll region; do not place the full PDF above or below the helper
- keep the voice state, current question, and composer/review action visible in
  the first working view where practical
- preserve PDF page, transcript position, pending proposal, current phase,
  voice session, and canonical values when switching views or rotating the
  device
- account for mobile browser toolbars, virtual keyboards, and safe-area insets
  without hiding the composer or creating horizontal overflow

Visual and interaction priorities:
- the current question, assistant response, listening state, and next valid
  action are primary
- the PDF remains the largest desktop visual surface and can be selected
  directly without displacing the conversation
- proposal review remains visually distinct from ordinary dialogue but uses
  concise human wording rather than another dense card stack
- advanced/manual controls stay collapsed by default and never compete with an
  ordinary interview turn
- use existing design tokens and components; do not introduce a component,
  layout, animation, icon, or state-management framework
- preserve visible focus, screen-reader status announcements, reduced motion,
  comfortable text size, contrast, and keyboard reachability

Acceptance criteria:
- at 1280 by 720 and 1440 by 900, the loaded app fits the browser viewport and
  does not require whole-page scrolling to see session state, active question,
  current response, and the composer or pending review controls
- the PDF and assistant have independent, predictable internal scrolling or
  page navigation and neither scroll moves the other pane
- microphone/listening state remains visible while reviewing conversation,
  answering, or waiting for the backend
- the active question and progress remain visible or immediately reachable
  without searching through old messages
- proposal review controls remain reachable without scrolling to a distant
  part of the page and retain every explicit safety action
- the composer remains reachable when the transcript grows, the PDF changes
  page, the assistant speaks, guidance opens, or an error appears
- on a 390 by 844 layout, no horizontal overflow occurs and switching between
  Assistant and Form preserves all session, page, transcript, proposal, and
  canonical state
- opening guidance, transcript history, assistance settings, or the manual
  drawer does not reset the active field or force the primary controls off
  screen without a clear close/return path
- keyboard focus order, Escape behavior, live regions, labels, and focus
  restoration work across both panes and every disclosure
- upload, extraction, PDF clicks, manual editing, typing, continuous voice,
  proposals, confirmation, preview filling, review, and download retain their
  existing shared-state behavior
- no backend, Form Agent, PDF Service, provider, model, voice-policy, or runtime
  dependency change is introduced by this milestone

Required automated testing:
- focused layout checks for viewport sizing, independent scroll owners, sticky
  session/question/composer regions, proposal visibility, and collapsed
  secondary controls
- state-preservation checks across desktop resizing, mobile view switching,
  rotation-like dimensions, long transcripts, long questions, guidance cards,
  errors, proposals, and virtual-keyboard-sized viewports
- accessibility checks for landmarks, status regions, keyboard order, visible
  focus, Escape/close behavior, focus restoration, labels, and reduced motion
- regression checks proving both panes remain mounted and no second canonical
  field or conversation store was introduced
- the complete established frontend and backend regression gate

Required visual/manual testing:
1. Capture and inspect upload, ready, listening, thinking, speaking, interrupted,
   proposal, clarification, error, paused, complete, review, and manual-editor
   states at 1280 by 720, 1440 by 900, and 390 by 844.
2. Grow a transcript beyond 50 messages and verify only the transcript scrolls
   while status, question, and answer/review controls remain reachable.
3. Navigate a multi-page PDF while the voice session continues and verify the
   assistant pane and canonical state do not move or reset.
4. Open every secondary disclosure and test the full workflow by keyboard and
   one screen-reader smoke path.
5. Open the mobile virtual keyboard and verify the active input and latest
   reply are not obscured.

Completion evidence to record:
- desktop and mobile screenshots for every named state
- viewport and overflow measurements
- keyboard and screen-reader smoke results
- long-transcript, multi-page PDF, proposal, and virtual-keyboard results
- focused layout/check commands and full regression output

Do not implement:
- new conversation intents, prompts, model behavior, voice capture policy, PDF
  semantics, widget geometry, authentication, persistence, analytics, or
  deployment
- a new frontend framework, state library, component system, CSS framework, or
  decorative redesign unrelated to the active task

# Milestone 9.2.5 — Integrated human-helper workflow validation

Status: NOT STARTED

Why this gate is required:
Milestones 9.2.2 through 9.2.4 deliberately separate conversation meaning,
voice turn-taking, and presentation. Each can pass in isolation while the
combined experience still feels robotic, loses an utterance, hides a proposal,
or makes the user hunt for controls. This milestone changes only reproduced
high-impact integration defects and establishes whether the product now feels
like a patient person sitting beside the user.

Goal:
Validate one uninterrupted, voice-first, context-aware form-completion
experience through the real frontend, Deepgram, Form Agent, Nemotron, PDF
preview, proposal confirmation, correction, final review, and download paths.
Use the evaluation harness and synthetic information to prove both human-helper
quality and exact canonical form correctness before release freeze.

Required fixed regression scenarios:
- support introduction: `Easier`, `make things clearer`, and `just start`
  produce natural setup behavior without requiring exact product wording
- identity: normal, duplicated, mixed-spelling, unfamiliar, corrected, and
  low-confidence names lead to a good proposal or targeted component question,
  never a guessed identity value
- explanation: the first `What does that mean?` explains the current field;
  repeated `Say it more simply` turns materially simplify rather than repeat
- date: spoken natural dates normalize only when unambiguous, and
  `05/19/2011` is clarified for a `DD/MM/YYYY` field
- dropdown: `I live by myself` asks about the missing tenure distinction and
  can never select `Living with family or friends`; `Solo tenant` may propose
  the exact `Sole tenant` option
- side question: `What if they live there but do not share costs?` is answered
  before returning naturally to the count question
- review: clear voice confirmation, rejection, repeat, edit, and correction
  operate through closed effects; `Permit`, vague agreement, background noise,
  and stale speech do not confirm anything
- hands-free rhythm: at least ten consecutive turns complete after one start,
  including a real interruption and a silent interval, without recording,
  interrupt, or retry button presses
- layout: the listening state, active question, latest response, proposal, and
  composer remain visible or immediately reachable throughout a long transcript
  and multi-page PDF
- recovery: one provider failure, network interruption, denied microphone,
  and paused session preserve the PDF and canonical state and allow typed/manual
  completion

Evaluation harness expansion:
- create a versioned `human-helper-experience-v2` suite from the observed
  transcripts and real extracted fixture schemas using synthetic facts only
- retain deterministic correctness and human-helper gates as separate results
- add route-selection, first-turn-help, progressive-simplification,
  finite-choice-safety, ambiguous-format, review-understanding,
  hands-free-continuity, false-interruption, silence-recovery, and
  control-hunting measurements
- score natural dialogue through observable behavior rather than exact sentence
  matching: addresses latest message, acknowledges useful content, asks only
  the missing distinction, avoids repetition, uses bounded context, and offers
  a useful next step
- retain exact effect, proposal, state, confirmation, invention, source, and
  PDF assertions as hard correctness requirements
- save full synthetic transcripts, route/fallback category, expected and actual
  state, visible UI state, timing, scores, and failure reasons
- compare only identical suite digests and model/provider configurations

Acceptance criteria:
- every scheduled deterministic turn completes with exact expected canonical
  state and zero invalid actions, invalid proposals, invented facts, invented
  purposes, unsafe transformations, or confirmation-boundary failures
- finite-choice safety is 100%; no related-but-insufficient utterance becomes
  an option without a focused clarification
- first-turn explanation success, latest-message adherence, context retention,
  progressive-simplification, clarification success, interruption recovery,
  and side-question recovery are each at least 90%
- repeated-response, redundant-question, unnecessary workflow-push,
  contradiction, false-interruption, duplicate-dispatch, and dropped-utterance
  rates are each at most 5%, with zero allowed for unsafe confirmation or
  invented personal information
- at least 90% of review decisions are understood on the first attempt, while
  ambiguous review language remains non-mutating
- the ten-turn hands-free scenario completes after one explicit start without
  mandatory record, interrupt, or retry actions
- the loaded desktop and mobile workflows do not require whole-page control
  hunting and retain one canonical state across PDF, conversation, voice, and
  manual editing
- sample and household-support fixtures complete from upload through reopened
  download with source bytes unchanged; one additional supported real-world
  fixture completes its selected hero subset
- provider, microphone, and network failures preserve confirmed values,
  pending review, transcript, current PDF, and manual fallback where technically
  possible
- any reproduced safety, data-loss, false-confirmation, invented-option, or
  source-PDF mutation failure blocks completion regardless of naturalness score
- the complete local regression gate, live provider suite, frontend visual QA,
  and reopened-PDF checks pass

Required automated testing:
- run the complete backend, PDF, Form Agent, transcript, safety, human-helper,
  Deepgram, interruption, workspace, accessibility, and production-build gates
- run `human-helper-experience-v2` first with deterministic provider doubles
  and then explicitly with configured Nemotron for the model-handled scenarios
- reopen every generated fixture PDF with `pypdf`, assert the demonstrated
  stored values, and prove each source fixture's bytes are unchanged
- save a digest-checked baseline/candidate comparison for every targeted repair
- scan tracked files, frontend output, and diagnostic artifacts for provider
  secrets or synthetic values that should remain local

Required end-to-end manual testing:
1. Complete the sample fixture from upload through reopened download by voice
   after one start, using a noisy/spelled name, explanation, rejection,
   correction, checkbox, interruption, silence, and final review.
2. Complete the household-support fixture with natural answers, an ambiguous
   date, `I live by myself`, a side question, skip/reopen, dropdown selection,
   and a corrected confirmed value.
3. Run the selected subset of one real official fixture and verify every shown
   question, option, prepared value, PDF update, and downloaded result.
4. Repeat a shorter typed-only path and verify identical transcripts yield the
   same effects and canonical values as voice.
5. Perform the flows at laptop and mobile sizes, with a 50-message transcript,
   keyboard-only navigation, and a screen-reader smoke pass.
6. Deny microphone permission and interrupt Nemotron, Deepgram, backend, and
   network availability one at a time; demonstrate recovery without starting
   the form over.

Completion evidence to record:
- suite version/digest, Git revision, model ID, Deepgram model/locale, fixture
  versions, browser/OS, scenario count, turn count, and field coverage
- full deterministic and live metric tables plus fixed/new/unchanged failures
- the three complete synthetic end-to-end transcripts and reopened-PDF results
- voice continuity, false/missed interruption, duplicate/drop, latency, layout,
  accessibility, and recovery results
- remaining known limitations stated plainly enough for README and demo use

Do not implement:
- unrelated features, additional languages, new PDF types, authentication,
  persistence, analytics, a database, Docker, or deployment
- a second agent, model debate, direct model effects, silent confirmation, or
  weakened safety thresholds merely to improve conversational scores
- Milestone 9.3, 9.4, deployment, or submission work before this integration
  gate actually passes

# Milestone 9.3 — One-language bilingual assistance pilot

Status: NOT STARTED — CONDITIONAL

Go/no-go gate before implementation:
- choose exactly one target assistance language
- arrange a fluent or native reviewer for that language
- select one English AcroForm demo fixture whose important questions and
  finite options the reviewer can validate
- confirm that the browser used for the demo supports speech recognition and
  speech synthesis for the selected language, or explicitly scope the pilot to
  typed assistance
- if these conditions are not met by 22 October 2026, defer this milestone to
  Milestone 12 and proceed directly to Milestone 9.4

Goal:
Help a speaker of one selected non-English language complete an English
fillable PDF while preserving the original form, exact field schema, user
facts, confirmation boundary, and required answer format.

Scope:
- require an explicit language choice; do not automatically infer language
- distinguish three separate concepts in state and UI:
  - source-form language
  - assistance/conversation language
  - language or format required for the value written into the form
- keep the original English question visible alongside the translated or
  simplified assistance
- allow the conversation, ordinary UI guidance, and supported browser voice
  output/input to use the selected language
- preserve stable field IDs, exact option values, stored names, identifiers,
  dates, numbers, addresses, and checked states
- do not translate names or identity data
- do not silently translate user-authored free prose into an English legal or
  official answer; explain the limitation and allow review/manual entry
- label translations as assistance, not official translations, unless the
  issuing organisation actually provides the reviewed translation
- use the existing single Form Agent and closed effects; do not introduce a
  translation agent or agent framework

Acceptance criteria:
- language choice is explicit, reversible, and session-only
- the original source question remains available at every assisted field
- the selected language improves explanation and interview wording without
  changing the field chosen, typed effect, finite option, proposed factual
  meaning, or canonical result
- names, IDs, dates, numbers, addresses, and finite choices survive language
  switching without semantic or character loss
- code-switching and an English answer during a non-English conversation are
  handled without losing the active field
- unsupported speech capability falls back clearly to typed bilingual help
- provider failure falls back to the existing English/manual workflow without
  clearing the PDF or confirmed values
- a fluent or native reviewer signs off the complete demo transcript and all
  user-visible translation strings
- the product claims support only for the one reviewed pilot language

Required automated testing after implementation:
- backend validation tests for supported, unsupported, missing, and malicious
  language values
- bilingual transcript fixtures covering explanation, answer, proposal,
  confirmation, rejection, correction, skip, progress, and completion
- parity tests asserting that equivalent English and pilot-language sessions
  produce the same stable field IDs, typed effects, finite options, and final
  canonical state
- Unicode tests for diacritics, non-ASCII names, apostrophes, hyphens, and the
  selected language's relevant script while preserving the user's spelling
- date, number, currency, address, checkbox, and dropdown tests that separate
  localized conversation wording from the value format required by the PDF
- adversarial tests for code-switching, prompt injection, a request to invent
  a missing fact, and an unsupported request to translate official free prose
- frontend checks for language selection, original-question visibility,
  switching language mid-session, accessible language labels, mobile layout,
  and typed fallback when speech support is absent
- the complete established local regression gate

Required live and human testing after implementation:
1. Have the fluent/native reviewer complete the chosen fixture using synthetic
   facts without reading an English script.
2. Repeat once with typing and once with voice if voice is in scope.
3. Deliberately code-switch, correct a confirmed value, ask what a field means,
   skip and reopen a field, then download and reopen the result.
4. Compare the completed PDF with an equivalent English run field by field.
5. Test denied microphone permission and a simulated Nebius failure.
6. Record every misleading, unnatural, or culturally inappropriate phrase;
   any meaning-changing issue blocks completion.

Completion evidence to record:
- selected language, fixture, reviewer role, and review date
- reviewed bilingual transcript using synthetic facts
- English-versus-bilingual canonical-state comparison
- browser and operating-system voice capability tested
- explicit list of unsupported translation cases

Do not implement:
- multiple languages, automatic language detection, foreign-language source
  forms, general document translation, or claims of certified translation
- silent translation of identity information or official free-text answers
- a second agent, translation framework, persistence, accounts, or analytics
- later deployment or submission work

# Milestone 9.4 — Hero workflow validation and release freeze

Status: NOT STARTED

Goal:
Choose the exact workflow judges will see, validate it with people who find
forms difficult, repair only reproduced high-impact failures, and freeze the
product before deployment.

Scope:
- select one primary hero fixture and one fallback fixture from the supported
  set; use synthetic information in every test
- document a short demo path that includes upload, a useful explanation,
  several conversational answers, an explicit review, one correction, a live
  PDF update, final review, and download
- run observed usability sessions with three to five people representing
  different support needs; ask what would help rather than diagnosing them
- measure completion, user effort, repeated questions, misunderstanding,
  confidence in what will be written, and recovery from one deliberate error
- convert every reproducible severe failure into a fixed automated scenario
  before making a targeted repair
- after acceptance, freeze feature scope and permit only release-blocking bug,
  security, accessibility, documentation, and deployment fixes

Acceptance criteria:
- at least three participants can complete the hero task with synthetic data
  without the facilitator telling them which product control to use
- every participant understands that an AI proposal is not written until it is
  confirmed
- no session invents a personal fact, silently changes a confirmed value,
  loses canonical state, overwrites the source PDF, or exposes a secret
- at least 80% of observed tasks complete successfully; any safety or data-loss
  failure is a hard failure regardless of the percentage
- the hero and fallback fixtures complete locally from upload through reopened
  downloaded PDF
- the fixed human-helper suite still passes both gates
- a provider/microphone-independent fallback demo can be completed
- open release-blocking findings have an owner or are resolved before freeze

Required automated testing after implementation:
- add fixed regression scenarios for every reproduced severe or repeated user
  failure; do not add tests that merely match one preferred sentence
- rerun the human-helper conversation harness on the unchanged suite digest
  and compare the candidate with the last passing report
- run the complete established local regression gate
- run the five-fixture API extraction/filling regression and reopen every
  generated PDF to check stored values and unchanged source bytes
- run a secret scan over tracked files and confirm `.env` remains ignored

Required manual testing after implementation:
1. Run three to five moderated sessions with synthetic data and no coaching.
2. Test the full hero route on a laptop at normal browser zoom.
3. Test the complete typed route and the complete voice route.
4. Test the 390-by-844 mobile layout, keyboard-only navigation, and a screen
   reader smoke path.
5. Deny microphone permission, disable the backend once, simulate one model
   failure, and prove progress can be recovered.
6. Run the fallback fixture and the offline/manual demo path.
7. Reopen downloaded PDFs with a normal PDF viewer and visually inspect every
   demonstrated value.

Completion evidence to record:
- hero and fallback fixtures
- anonymized task results and observed failure list, with no personal data
- before/after harness report comparison for any repair
- frozen demo script and fallback script
- final known-issues list and explicit feature-freeze date

Do not implement:
- new feature categories discovered during testing unless they block the hero
  workflow's safety or completion
- new PDF types, additional languages, authentication, persistence, a
  database, analytics, online forms, or infrastructure beyond local testing
- deployment or submission work before the release candidate passes

# Milestone 10 — Deployment

Status: NOT STARTED

Goal:
Deploy the frozen frontend and backend with secure configuration suitable for
the hackathon demonstration.

Scope:
- choose the smallest hosting arrangement that supports the existing React
  build, FastAPI service, temporary PDF processing, HTTPS, health checks, and
  server-side environment variables
- record the hosting choice and any architecture-impacting operational
  constraint before implementation
- configure only the deployed frontend origin in production CORS
- keep Nebius and Tavily credentials in backend host secrets; never expose them
  through Vite variables, frontend bundles, logs, or repository files
- define explicit upload-size, provider-timeout, application-timeout, and
  user-facing failure behaviour
- use temporary request processing only and do not introduce document or
  transcript persistence
- add only essential structured logs that exclude PDF bytes, field values,
  conversation text, provider keys, and other user content

Acceptance criteria:
- frontend and backend are reachable over HTTPS
- production CORS is restricted to the deployed frontend
- Nebius and Tavily credentials remain server-side
- health checks and essential privacy-safe logs are available
- invalid, non-PDF, oversized, timed-out, and provider-failed requests fail
  clearly without losing the current browser session
- one production request cannot overwrite the uploaded source PDF
- deployed upload, extraction, conversation, confirmation, preview, review,
  fill, and download work with the frozen hero fixture
- microphone features run only in the secure browser context and retain typed
  fallback
- no user document or transcript persistence is introduced without a separate
  explicit decision

Required automated testing after implementation:
- run the complete established local regression gate against the release
  revision
- build the exact frontend artifact used for deployment from a clean checkout
- run backend configuration tests for the production CORS allowlist, missing
  secrets, upload-size limits, non-PDF input, provider timeout, and controlled
  service errors
- run an HTTPS smoke script against the deployed API covering `/health`, PDF
  extraction, at least one Form Agent turn, PDF fill, download, and reopening
  the result to verify its value
- verify an allowed CORS origin succeeds and an unlisted origin is rejected
- scan the built frontend, source tree, tracked files, and deployment logs for
  secret values and provider keys

Required manual testing after implementation:
1. Open the deployed URL in a private/incognito window on a second device or
   clean browser profile.
2. Run the frozen hero script from upload to reopened download.
3. Repeat the critical path with typing, then test voice permission and speech
   on the actual demo browser.
4. Deny microphone permission and prove the typed fallback completes.
5. Temporarily use a controlled invalid provider configuration or mock failure
   and verify a recoverable message with no lost confirmed values.
6. Upload an invalid file and an over-limit fixture and verify clear errors.
7. Restart or redeploy the backend, verify `/health`, and repeat the smoke path
   to catch cold-start or temporary-filesystem assumptions.
8. Inspect browser network requests, built assets, host logs, and temporary
   storage to verify no key or retained user document is present.

Completion evidence to record:
- public frontend URL and backend health URL
- deployed Git revision
- hosting and configuration decision
- automated HTTPS smoke result
- browser/device matrix and voice capability result
- CORS, secret-scan, size-limit, timeout, restart, and no-persistence evidence
- rollback/redeploy command or documented provider action

Do not implement:
- accounts, authentication, document history, database storage, analytics,
  background jobs, autonomous submission, Docker, or an orchestration platform
  unless the selected host strictly requires it and the change is separately
  justified
- new conversation, language, PDF, or user-interface features after freeze

# Milestone 11 — Hackathon submission

Status: NOT STARTED

Goal:
Package a clear, repeatable demonstration of the conversation-first form
assistant and its required NVIDIA/Nebius technology.

Submission deliverables:
- working hosted demo or clearly testable application
- public GitHub repository with the existing open-source licence
- current README covering setup, environment variables, architecture, local
  frontend/backend commands, testing, limitations, and deployment
- public YouTube demonstration video no longer than three minutes
- Devpost description, selected `Best Apps and Agents` track, screenshots, and
  working links
- clear explanation of how NVIDIA Nemotron and Nebius Token Factory are used
  at runtime
- feedback on the NVIDIA and Nebius technologies used

Acceptance criteria:
- the demo shows upload, explanation, voice or typed guidance, explicit
  confirmation, live PDF update, review, correction, and download
- the submission clearly identifies Nemotron and Nebius Token Factory usage
  without implying that deterministic PDF or state logic is performed by AI
- setup and local-run documentation works from a clean checkout
- architecture, privacy, no-invention, canonical-state, and confirmation
  boundaries are explained accurately
- the public repository contains no `.env`, API key, personal data, generated
  user document, or private evaluation artifact
- the demo has a tested fallback path if microphone access, Tavily, Nemotron,
  or the hosted service is unavailable
- all public links work without the submitter's signed-in browser session
- the final submitted build matches the tested deployed Git revision

Required testing before submission:
- run the complete established local regression gate one final time
- run the deployed HTTPS smoke test and frozen hero script immediately before
  recording and again before submission
- follow the README from a clean clone or fresh environment and record any
  missing step; a familiar development environment is not sufficient evidence
- inspect `git status`, tracked files, commit history, the production frontend
  bundle, screenshots, video frames, and documentation for secrets or personal
  information
- test repository, hosted demo, YouTube, and Devpost links in an incognito
  window while signed out
- rehearse the three-minute demo at least three times and keep one version that
  finishes with time for the completed PDF result
- verify video audio, captions, text legibility, synthetic data, and the visible
  NVIDIA/Nebius runtime explanation
- perform one rehearsal with the fallback script and locally retained demo
  assets so a provider, network, or microphone problem does not end the demo

Required manual submission checklist:
1. Confirm the repository is public and the licence is visible.
2. Confirm no secret exists in the repository or frontend bundle; rotate any
   credential if exposure is suspected.
3. Confirm README commands work exactly as written.
4. Confirm the hosted demo opens and the health endpoint is healthy.
5. Confirm the video is public, no longer than three minutes, and audible.
6. Confirm Devpost names the track and explains the user problem, workflow,
   real-world impact, originality, NVIDIA model, and Nebius runtime calls.
7. Confirm the technology feedback is specific and truthful.
8. Open every submitted link while signed out.
9. Save the final submission confirmation and do not begin a new milestone
   before the deadline.

Completion evidence to record:
- release Git revision and final regression output
- clean-clone verification environment
- hosted URLs and signed-out link-check result
- final video duration and rehearsal result
- completed official submission checklist and confirmation
- known limitations stated in README and Devpost

Do not implement:
- last-minute new features, new providers, new models, new PDF types, new
  languages, authentication, persistence, or infrastructure unrelated to a
  release-blocking issue
- claims that were not demonstrated or measured

# Deferred post-hackathon roadmap

The milestones below require a fresh decision after submission. Their order may
change based on user evidence. They must not be pulled into Milestones 9.1–11.

## Milestone 12 — Reviewed multilingual assistance expansion

Status: DEFERRED UNTIL AFTER SUBMISSION

Goal:
Expand assistance-language support for English source PDFs one reviewed
language at a time, using the Milestone 9.3 safety and parity boundary.

Required testing after each added language:
- fluent/native review of all interface strings and complete synthetic
  transcripts
- English-versus-target-language canonical-state and effect parity
- per-language typed, code-switched, correction, guidance, and completion
  transcript suites
- Unicode, date, number, currency, address, names, finite-choice, and PDF-font
  coverage appropriate to the language
- supported browser speech-recognition and speech-synthesis checks when voice
  is claimed; otherwise an explicit typed-only support label
- accessibility review for language metadata, pronunciation, focus order, text
  expansion, and right-to-left layout when relevant
- provider-failure and English/manual fallback checks
- complete regression gate with zero invention or confirmation regression

Completion rule:
Do not add a language to the public support matrix until its reviewer and test
evidence pass. Model fluency or automated translation alone is insufficient.

## Milestone 13 — Foreign-language source-form research and pilot

Status: DEFERRED UNTIL AFTER SUBMISSION

Goal:
Determine whether Formless can safely help an English or bilingual user
complete a form whose source language is not English, then implement one
reviewed pilot only if extraction, field meaning, answer-language requirements,
and PDF rendering can be validated.

Required testing after the research and any pilot:
- corpus review with legally reusable fillable fixtures in one source language
- exact field-ID, widget, option, order, and label extraction comparison by a
  fluent reviewer
- tests that separately preserve source language, assistance language, and the
  value language/format required by the form
- no-guess tests for unreviewed legal, eligibility, declaration, or signature
  wording
- completed-PDF rendering and font/glyph checks in ordinary viewers
- bilingual transcript, correction, final-review, and download tests
- explicit unsupported-document and unsupported-language fallbacks
- complete regression gate

Completion rule:
Research may conclude `do not support yet`; that is a valid outcome. Do not
present machine-translated form meaning as official guidance.

## Milestone 14 — Non-AcroForm document discovery and support decision

Status: DEFERRED UNTIL AFTER SUBMISSION

Goal:
Evaluate static PDFs, scanned PDFs, and XFA separately before deciding whether
to add OCR, field-region mapping, or a conversion workflow. Do not treat these
formats as variants of the current reliable AcroForm path.

Required testing after research and before any support claim:
- a versioned corpus for digital static, scanned, and XFA documents
- deterministic format classification with clear unsupported explanations
- page-text/OCR accuracy, field-to-question alignment, confidence, and
  no-silent-mapping measurements
- visual region and completed-output review across rotation, scale, multi-page,
  handwriting, poor scan, and complex-choice cases
- explicit human review before any inferred field mapping can become writable
- source-byte preservation and separate output-file checks
- privacy and provider-boundary review before any PDF page or OCR result can be
  sent externally
- complete AcroForm regression gate

Completion rule:
Choose one format and one narrow workflow only after the research evidence.
OCR, XFA, free-form annotation, and general document understanding must not be
implemented together as one milestone.

## Milestone 15 — Production trust, privacy, and operating model

Status: DEFERRED UNTIL AFTER SUBMISSION

Goal:
Decide what a real public service needs beyond the ephemeral hackathon app,
including retention, deletion, security, abuse controls, observability, and
whether accounts or persistence are necessary at all.

Required testing after any production-readiness implementation:
- written threat model and data-flow review covering PDF bytes, answers,
  transcripts, provider calls, logs, temporary files, and secrets
- retention/deletion tests and proof that the documented policy matches actual
  storage behaviour
- authorization and tenant-isolation tests if accounts are introduced
- upload abuse, malformed PDF, rate-limit, timeout, dependency-failure, and
  resource-exhaustion tests
- dependency and secret scanning, privacy-safe log inspection, backup/deletion
  checks where storage exists, and incident/credential-rotation rehearsal
- accessibility and supported-browser regression
- complete conversation, PDF, multilingual, and deployment regression gates

Completion rule:
Do not add authentication, a database, persistent transcripts, document
history, or analytics by default. Each requires an explicit user need,
architecture decision, privacy boundary, and testable deletion story.
