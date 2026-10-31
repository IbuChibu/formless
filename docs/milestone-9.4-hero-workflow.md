# Milestone 9.4 hero workflow

## Release candidate

- Primary fixture: `household_support_review_demo.pdf`
- Fallback fixture: `sample_form.pdf`
- Information used in every run: synthetic only
- Runtime model: `nvidia/Nemotron-3_5-Lightning`
- Feature scope: frozen after the automated 9.2.5 release gate on 30 October
  2026; only release-blocking safety, accessibility, state-loss, and
  documentation fixes are permitted

The household-support fixture is the hero because it demonstrates confusing
official wording, dates, a finite housing choice, a count side-question,
skip/reopen, correction, explicit review, live PDF updates, and download. The
sample form is the reliable provider-independent fallback.

## Synthetic hero path

1. Upload the household-support fixture and choose simpler wording and a slow,
   one-question-at-a-time interview.
2. Ask what `Date occupancy commenced` means, then ask for a simpler version.
3. Answer with an unambiguous synthetic date and confirm the visible proposal.
4. At housing arrangement, say `I live by myself`; verify Formless asks whether
   the user rents, owns, or has another arrangement and does not choose one.
5. Say `Solo tenant`, review `Sole tenant`, and confirm.
6. Ask what happens when a resident does not share food or costs; verify the
   answer returns to the count question.
7. Give `Two, including me`, reject it, correct it to `one, just me`, and
   confirm.
8. Skip the preferred-name question, reopen it conversationally, enter `Jordy`,
   and confirm.
9. Open final review, verify the canonical values against the PDF preview,
   download the completed copy, and reopen it in a normal PDF viewer.

Fallback path: upload `sample_form.pdf`, type a synthetic full name, select a
country, confirm the terms checkbox, review, download, and reopen. This path
must remain usable with the microphone denied and the model unavailable.

## Observed-session gate

Run the hero path with at least three people who find some aspect of forms
difficult. Do not diagnose participants and do not tell them which control to
use. Record only anonymous results and synthetic form values.

For each session record:

- task completion and where help was required
- whether the participant understood that proposals are not written until
  confirmed
- repeated questions or misunderstood responses
- confidence in what would be written
- recovery from one deliberate incorrect answer
- control hunting, missed voice state, or hidden transcript/composer
- any invented fact, false confirmation, state loss, source overwrite, or
  secret exposure (each is an immediate release blocker)

The milestone can be marked complete only when at least three sessions have
run, at least 80% of observed tasks succeed, every participant understands the
confirmation boundary, and no safety or data-loss blocker remains.

## Automated evidence already passing

- 493 backend tests
- 40 focused five-fixture PDF extraction/fill/reopen compatibility tests
- all frontend PDF workflow, workspace, fixed-layout, interruption, continuous
  voice, Deepgram, reliability, support-preference, and production-build gates
- `human-helper-experience-v2`: 5 scenarios, 32 turns, exact state and all
  measured human-helper rates at 100%, zero invention or confirmation failures
- tracked-secret scan: no real provider credential present

## Still required before freeze

- three to five observed human sessions
- a physical one-start microphone run with interruption and silence recovery
- loaded-form checks at 1280x720, 1440x900, and 390x844
- keyboard-only and screen-reader smoke tests
- downloaded-PDF visual inspection for the hero and fallback flows
