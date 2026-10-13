# Milestone 7.2 conversation evaluation baseline

Recorded: 13 October 2026

Suite: `guided-interview-baseline-v1`

Target: the in-process public `FormAgentService.respond` boundary using the
configured `nvidia/Nemotron-3_5-Lightning` model. The optional qualitative
rubric used the same configured Nemotron service. All persona details and form
answers were synthetic.

## What was evaluated

Eight personas ran 47 scheduled turns across eight scenarios using fields
extracted from the sample, household-support, and USCIS I-9 PDF fixtures:

1. multiple fields in one message
2. correction of a previously confirmed answer
3. an ambiguous and incomplete date
4. a field explanation and contextual follow-up
5. an interruption to ask about progress
6. skipping and reopening a field
7. confusion and frustration with formal wording
8. returning to an earlier confirmed question

The full generated JSON and Markdown transcripts are written locally under
`backend/evaluations/results/` and deliberately ignored by Git. Rerunning the
documented command regenerates them from the versioned scenario suite.

## Baseline metrics

| Metric | Result |
| --- | ---: |
| Completed scheduled turns | 42 / 47 (`0.894`) |
| Exact form-state accuracy | `0.500` |
| Context-retention rate | `0.619` |
| Recovery success rate | `0.333` |
| Unnecessary repetition rate | `0.062` |
| Heuristic clarification quality | `4.667 / 5` |
| Heuristic naturalness | `4.938 / 5` |
| Judged naturalness | `3.875 / 5` |
| Judged context awareness | `3.625 / 5` |
| Judged clarification quality | `3.833 / 5` |
| Judged recovery quality | `3.600 / 5` |
| Deterministic invented-value failures | `0` |
| Average Form Agent turn latency | `109.269 ms` |

The latency is the measured Form Agent response time for these turns, many of
which route deterministically; it does not include the separate qualitative
judge call. Qualitative scores are supporting evidence only and do not override
incorrect canonical state.

## What already works

- Explicit proposals and confirmations remain separate.
- A confirmed value stays in place until a replacement is explicitly
  confirmed.
- The complete correction scenario passed and preserved another confirmed
  field.
- Skipping, reopening, and then confirming a field followed closed effects.
- The frustrated user received an empathetic, simpler question and completed
  the field without repetition.
- No deterministic check found a proposal containing information absent from
  the synthetic user's messages or declared safe normalization.

## Biggest weaknesses

1. A bundled name and date was treated as an ambiguous name, and the later date
   was not recovered from history.
2. Conversational wrappers were stored as field values: `Please call me Alex`
   instead of `Alex`, and `Okay, my first name is Jordan` instead of `Jordan`.
3. Complete month-name dates such as `the sixth of March 1992` and `I moved in
   on 2 September 2021` did not become safe date proposals.
4. A progress interruption preserved the active field and counts, but did not
   identify the confirmed answer the user expected to hear.
5. `Can we go back to the full name question?` did not enter the existing
   correction flow, so the next cancellation was interpreted against Country.
6. Fluent and empathetic prose scored well even where exact form state failed.
   This confirms that form-state metrics must gate prompt or model changes.

## Targeted next changes

Milestone 7.3 should make small, field-aware changes for answer-wrapper
extraction, unambiguous spoken dates, bounded use of volunteered context,
natural return-to-field navigation, canonical progress answers, and
schema-grounded format guidance. It must then rerun this exact suite and compare
the candidate report against this baseline before any result is accepted.
