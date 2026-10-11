# Milestone 6.16 guided-interview reference

## Purpose

This document records the interaction qualities Formless should reproduce for
Milestone 6.16. It is a durable local reference for the experience demonstrated
by the public ChatGPT conversation titled `Complete Form Together`:

https://chatgpt.com/share/6acbbd18-a678-83eb-9942-389daa14d6c6

The external conversation is an illustrative design reference, not a product
dependency or source of form instructions. If the shared link becomes
unavailable, this document remains the authoritative description of the useful
interaction pattern. `PROJECT_PLAN.md`, `ARCHITECTURE.md`, and `DECISIONS.md`
remain authoritative for scope, architecture, and safety.

## Full source conversation reconstruction

This is a complete turn-by-turn reconstruction of the shared conversation as
inspected on 11 October 2026. It preserves the interaction, answers, question
sequence, controls, review, and outcome. Assistant wording is paraphrased rather
than presented as a verbatim archival export. The source conversation contains
form-related assertions that have not been adopted as Formless requirements;
the safety notes later in this document identify the important differences.

### Turn 1 — Agreeing on the workflow

**User**

Asks whether they can upload a PDF, work through it collaboratively one question
at a time, and receive all the answers at the end.

**Assistant**

Agrees and outlines this process:

1. Upload and inspect the PDF.
2. Ask one question and wait for the answer before continuing.
3. Discuss uncertain questions and help turn rough thoughts into usable answers.
4. Maintain a numbered record of answers.
5. Review every question and answer at the end.
6. Produce either a separate answer document or a filled original PDF when its
   format supports that.

It also says that questions can be skipped, revisited, or changed and that it
will not answer factual questions on the user's behalf without discussion.

### Turn 2 — Upload and first question

**User**

Uploads a PDF.

**Assistant**

Identifies the document as the four-page USCIS Form I-9 and says the interview
will begin with Section 1 on page 1. It explains that Section 2 is generally an
employer responsibility.

It then displays:

- section: Employee Information
- question 1: last or family name as shown on official documents
- control: text input for the family name
- secondary guidance: questions can be skipped, and sensitive identifiers can
  be left as placeholders instead of being disclosed in chat

### Turn 3 — Last name

**User**

Enters `michael`.

**Assistant**

Records and displays the value as `Michael`, then asks question 2: the user's
first or given name as shown on official documents. It presents a text input.

### Turn 4 — First name

**User**

Enters `johnathan`.

**Assistant**

Records and displays `Johnathan`, briefly summarizes the name collected so far,
and asks question 3: the user's middle initial, if any.

Controls:

- a short text input for the initial
- a `No middle initial` shortcut

### Turn 5 — Middle initial

**User**

Enters `V`.

**Assistant**

Acknowledges the middle initial, summarizes the assembled name as `Johnathan V
Michael`, and asks question 4: whether the user has used any other family names,
including a previous or legally changed surname.

Controls:

- `No`
- `Yes`

### Turn 6 — Other last names

**User**

Says that no other last names have been used.

**Assistant**

Records the answer as none and asks question 5: the street number and street
name of the user's current residential address. It explains that apartment,
city, state, and ZIP information will be collected separately.

Control: street-address text input.

### Turn 7 — Street address

**User**

Enters `123 main street`.

**Assistant**

Displays the prepared capitalization as `123 Main Street` and asks question 6:
whether there is an apartment or unit number.

Controls:

- optional apartment or unit text input
- `No apartment number` shortcut

### Turn 8 — Apartment number

**User**

Says there is no apartment number.

**Assistant**

Records the apartment field as none and asks question 7: the city or town where
the user lives. It presents a text input.

### Turn 9 — City

**User**

Enters `Chicago`.

**Assistant**

Acknowledges Chicago and asks question 8: the user's state. The example presents
`Illinois (IL)` as a selectable value with a next-question action.

### Turn 10 — State

**User**

Selects `Illinois (IL)`.

**Assistant**

Acknowledges the state and asks question 9: the five-digit ZIP code. It notes
that the ZIP should correspond to the Chicago, Illinois residential address and
presents a ZIP text input.

### Turn 11 — ZIP code

**User**

Enters `60601`.

**Assistant**

Acknowledges the ZIP code and asks question 10: date of birth. It requests the
date in `MM/DD/YYYY` format and presents a date text input.

### Turn 12 — Date of birth

**User**

Enters `10/10/1987`.

**Assistant**

Acknowledges both the numeric date and its human-readable interpretation, then
asks question 11: the user's US Social Security Number.

It describes the expected nine-digit pattern and offers privacy-oriented
choices instead of requiring the number in chat:

- enter the SSN privately later
- indicate that the user does not have a US SSN

The response also makes a form-specific statement about when the SSN may be
optional. Formless must not reproduce that kind of assertion without verified,
version-appropriate guidance.

### Turn 13 — Social Security Number

**User**

Requests that the SSN remain out of the chat and be entered privately into the
PDF.

**Assistant**

Marks the SSN for later private entry, says it will leave that PDF field blank,
and asks question 12: the user's email address.

Controls:

- email text input
- `Skip email` shortcut

The example describes the field as optional. Formless should show that statement
only when supported by verified metadata or guidance.

### Turn 14 — Email address

**User**

Enters `johnathan@email.com` with conversational framing.

**Assistant**

Extracts and acknowledges `johnathan@email.com`, then asks question 13: the
user's telephone number.

Controls:

- telephone text input
- `Skip telephone` shortcut

### Turn 15 — Telephone number

**User**

Requests that the telephone number remain blank.

**Assistant**

Acknowledges the blank telephone field, marks the personal-information portion
as complete, and moves to the Employee Attestation subsection.

It asks question 14: which citizenship or immigration status applies. Four
radio-style options are presented:

1. Citizen of the United States
2. Noncitizen national of the United States
3. Lawful permanent resident
4. Alien authorized to work in the United States

It notes that some choices may require further immigration information.

### Turn 16 — Citizenship status

**User**

Selects option 1, citizen of the United States.

**Assistant**

Acknowledges the selection, states that no additional immigration document
numbers are needed in Section 1 for that path, and asks question 15: whether the
user is ready to sign and date Section 1.

It explains the significance of the signature, says the signature can remain
blank for the user to add personally, and presents two choices:

- leave space for the user's signature
- review answers first

### Turn 17 — Signature and date

**User**

Requests that the employee-signature field remain blank for personal signing
and asks to use 11 October 2026 as the current date.

**Assistant**

Acknowledges the blank signature and prepares the date as `10/11/2026`. It then
moves to the Preparer/Translator subsection and asks question 16: whether anyone
assisted in preparing or translating the form.

Controls:

- no other person assisted; answers were supplied by the user with AI guidance
- another person helped prepare or translate the form

The assistant says Supplement A exists for a preparer or translator and suggests
establishing whether a person also assisted. Formless must avoid implying that
AI assistance determines the legal preparer/translator answer.

### Turn 18 — Preparer or translator and final review

**User**

Says that no person assisted and that the answers were supplied personally with
AI guidance.

**Assistant**

Records that no other person assisted. It provisionally treats Supplement A as
blank while suggesting employer confirmation, says the employee section is
complete, and explains that Section 2 remains for the employer or authorized
representative.

It then presents a final review table:

| Field | Reviewed value |
| --- | --- |
| Full name | Johnathan V Michael |
| Other last names | None |
| Address | 123 Main Street |
| City, State, ZIP | Chicago, IL 60601 |
| Date of birth | 10/10/1987 |
| Social Security Number | Enter privately |
| Email | johnathan@email.com |
| Telephone | Blank |
| Citizenship | US citizen |
| Signature | Sign personally |
| Date | 10/11/2026 |
| Preparer/Translator | No other person |

Controls:

- confirm that everything is correct
- indicate that something needs changing
- prepare the completed PDF after confirmation

### Turn 19 — Completion

**User**

Confirms the Section 1 details and requests a completed PDF with the SSN and
signature blank and Section 2 reserved for the employer.

**Assistant**

Generates a four-page completed Form I-9 and provides a download action. It says
Section 1 was populated from the supplied answers and lists the deliberately
blank areas:

- Social Security Number for private entry
- employee signature for personal signing
- Section 2 for the employer or authorized representative
- Supplements A and B

It finishes with a short before-submission checklist covering private SSN entry
when applicable, personal signature, verification of the information, and the
employer's Section 2 work. It also offers follow-up actions to summarize the
conversation, discuss employer instructions, or create a completed-versus-
pending checklist.

## Experience being referenced

The example turns a long PDF form into a guided interview. Instead of exposing
all fields at once, it asks one question, accepts an answer, acknowledges it,
and proceeds to the next relevant question. It supplies brief context only when
useful and uses simple controls for constrained answers.

The useful rhythm is:

1. Identify the current section and question.
2. Ask one question in direct language.
3. Accept a natural-language answer or a field-appropriate quick choice.
4. Acknowledge what was understood.
5. Progress to the next question without a separate Continue step.
6. Allow explanation, skipping, correction, and later review without losing
   the user's place.
7. At completion, summarize entered and blank information before producing the
   final document.

The example also demonstrates useful presentation details:

- a long form feels like a sequence of manageable questions
- the assistant references the real field rather than an internal field ID
- date and option formats are stated at the point they matter
- optional or sensitive questions can be deferred
- finite choices are presented as clear selectable options
- each answer receives a short acknowledgement before progression
- the final review uses recognizable field labels and values
- remaining blank or employer/issuer-completed sections are called out clearly

## Formless adaptation

Formless should reproduce the pacing and clarity while retaining stronger
safety boundaries than the reference conversation.

### One focused question

The active question is the visually dominant task. Show its section, page, and
supported-field progress when those values are available from extracted
metadata. Keep the PDF visible beside the interview.

Example:

```text
Personal details · Question 4 of 12

What is your date of birth?
Please use day, month, and year.
```

### Natural answering with useful controls

The typed composer remains available for every supported field. A checkbox,
radio group, or dropdown may additionally show quick-answer controls built only
from validated schema options. Quick controls and typed answers must use the
same Form Agent event path.

### Explicit proposal review

Unlike the reference conversation, Formless must not treat the assistant's
interpretation as immediately accepted. An answer first becomes a pending,
validated proposal.

```text
You said
17 October 1986

Prepared for the form
17/10/1986

Formatted as DD/MM/YYYY.

[Confirm] [Edit] [Use original] [Reject]
```

The currently displayed PDF changes only after an explicit confirmation or an
explicit manual edit.

### Concise progression

After confirmation or skip, acknowledge the resolved question and ask the next
one in the same turn:

```text
Added your date of birth.

Next, when did you begin living at your current address?
```

Do not require a routine Continue action between questions. Do not append the
same menu of conversational commands to every assistant response.

### Explanation and repair

If the user asks what a question means, answer that request directly and retain
the active field. Repeated explanation requests must become simpler or approach
the wording differently rather than repeating the same sentence.

```text
User: What does "date occupancy commenced" mean?
Assistant: It means the date you started living at your current home.

User: Explain it more simply.
Assistant: When did you move into the home where you live now?
```

Explanations must not invent why the organisation requests the information.
Questions about official requirements, purposes, or legal effect remain on the
reviewed-guidance and policy-gated Tavily path.

### Review and correction

The user should be able to ask what is confirmed, skipped, or unanswered and
refer to a field conversationally. A confirmed answer remains canonical while
a replacement is being discussed. The replacement must be explicitly
confirmed before it reaches the PDF.

At `form_complete`, provide a concise conversational summary and routes to
review or correct answers. The dedicated visual final-review workspace remains
part of Milestone 8.

## Interaction sketch

```text
Assistant
Personal details · Question 4 of 12
What is your date of birth? Please use day, month, and year.

User
17 October 1986

Assistant
I understood your date of birth and prepared it in the format requested by the
form.

Proposal card
You said: 17 October 1986
Prepared for the form: 17/10/1986
Change: formatted as DD/MM/YYYY
[Confirm] [Edit] [Use original] [Reject]

User explicitly confirms

Assistant
Added your date of birth. Next, when did you begin living at your current
address?

User
What does that mean?

Assistant
When did you move into the home where you live now?

User
June 2019, but I do not remember the day.

Assistant
You know the month and year but not the exact day. The form asks for a complete
date, so I will not guess the missing day. Would you like to leave this for now
or check your records?
```

## What to adopt

- one-question-at-a-time pacing
- visible section and progress context
- short, specific acknowledgements
- natural typed answers plus schema-derived quick controls
- context-sensitive help rather than repeated canned menus
- automatic progression after an explicit proposal decision
- conversational navigation, correction, and review
- a clear completion summary and next steps

## What not to copy

- silently accepting or applying an interpreted answer
- treating ordinary `yes`, `okay`, or `change it` messages as confirmation
- making unsupported claims about whether a field is optional or required
- inventing why an organisation asks a question
- treating AI assistance as a human preparer, legal adviser, or official source
- hiding the PDF until the end of the interview
- creating a second state model for quick controls or future voice input
- allowing assistant prose to mutate form or PDF state

## Relationship to later milestones

- Milestone 6.15 provides conversational navigation, reopening, correction, and
  canonical review operations used by this interface.
- Milestone 6.16 presents those capabilities as a focused typed interview.
- Milestone 7 adds speech input and output around the same interview and Form
  Agent events; it does not create a separate voice agent.
- Milestone 8 adds active-field PDF navigation and highlighting, direct PDF
  field editing, and the dedicated final-review workspace.
