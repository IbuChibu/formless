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

- completed through Milestone 6.13.10
- current typed workflow separates conversation from validated form effects
- completed through Milestone 6.14
- Milestone 6.15 is the next planned milestone before the guided-interview UI
- Milestone 6.16 is planned after conversational navigation and before voice
- voice, deployment, persistence, and the later full-workflow milestone have
  not started

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

Status: NOT STARTED

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

Status: NOT STARTED

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
