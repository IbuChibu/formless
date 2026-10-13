# Milestone 7.3 conversation reliability result

Recorded: 13 October 2026

The candidate ran the unchanged `guided-interview-baseline-v1` scenario file
with suite digest `c5d8e5503835468a`. It used the in-process public
`FormAgentService.respond` boundary and the configured
`nvidia/Nemotron-3_5-Lightning` model. Generated JSON, Markdown transcript, and
comparison artifacts remain local under `backend/evaluations/results/` and are
ignored by Git.

## Accepted changes

- Names are separated from common conversational wrappers and from an
  unrelated date volunteered in the same message.
- Unambiguous spoken ordinal dates are parsed conservatively and formatted only
  when the extracted field schema requests a format.
- An explicit reference to an earlier answer can recover exactly one
  field-specific, adapter-validated date from bounded request history.
- Natural `go back to` wording can enter the existing closed correction flow,
  and conversational cancellation returns to the unanswered field without
  changing the confirmed value.
- Progress and status reviews can name confirmed canonical values.
- The trusted model prompt prohibits presenting a format as required unless it
  is present in the extracted schema or verified guidance.

Every recovered or prepared value remains an unconfirmed proposal. Only the
existing explicit confirmation event can update canonical state or reach PDF
filling.

## Comparison

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Completed scheduled turns | `0.894` (42/47) | `1.000` (47/47) | `+0.106` |
| Exact form-state accuracy | `0.500` | `0.875` | `+0.375` |
| Context retention | `0.619` | `1.000` | `+0.381` |
| Recovery success | `0.333` | `0.857` | `+0.524` |
| Unnecessary repetition | `0.062` | `0.000` | `-0.062` |
| Deterministic failures | `34` | `3` | `-31` |
| Invention failures | `0` | `0` | `0` |

The optional qualitative judge scored the candidate `5/5` for naturalness,
context awareness, clarification quality, and recovery. It also recorded one
qualitative format mismatch for the same occupancy-date difference described
below. Deterministic state remains the acceptance authority.

## Residual mismatch

The candidate has one presentation-only mismatch spanning three checks in one
scenario. The occupancy-date field's extracted question, label, and help text
do not specify a required format. The user says `2 September 2021`; the agent
therefore keeps that unambiguous wording instead of silently changing it to the
scenario's expected `02/09/2021`. The value is proposed, explicitly confirmed,
and stored successfully. The separate frustration scenario similarly preserves
`14 January 2020`, so adding a field-specific hidden format assumption would be
inconsistent and less safe.

## Verification

- 323 backend tests passed.
- The 47-turn curated transcript evaluation passed with zero failures, invalid
  actions, invalid proposals, confirmation-boundary failures, invention
  failures, or unsafe transformations.
- The 14-scenario single-turn safety evaluation passed with zero failures.
- The frontend production build passed; the existing Vite bundle-size warning
  remains non-blocking.
