# Milestone 7.4 voice-like conversation reliability result

Recorded 14 October 2026.

## Why this benchmark exists

A real turn-based voice interview was generally transcribed correctly, but the
assistant sometimes behaved like a rigid form validator. The most visible
failure was a stale-answer loop: after the user clarified `Nobody` with the new
answer `One`, the assistant repeated its response to `Nobody` and asked about
zero again.

Milestone 7.4 turns that session into a fixed synthetic regression suite before
changing production behavior. The suite uses only fields extracted from the
checked-in household-support PDF fixture.

## Fixed scenarios

- explain an occupancy-date question without inventing a required format or
  acceptable precision
- interpret `Solo tenant` as the single high-confidence `Sole tenant` option,
  while retaining explicit review
- clarify `Nobody` on a question that says to count yourself, then treat the
  newer answer `One` as `1`
- make a `confirm_edit` acknowledgement show that the reviewed edited value,
  rather than the earlier proposal, was used

The harness now supports per-turn required phrases, forbidden phrases, and
response-length bounds. It separately reports latest-answer adherence and
assistant contradictions. Those metrics are not scored for suites that contain
no matching tagged turns.

## Live before-and-after evidence

Both reports used Nemotron through Nebius Token Factory and the same suite
digest: `d8aac2d7708deb62`.

| Metric | Baseline | Final candidate |
| --- | ---: | ---: |
| Completed turns | 1.000 | 1.000 |
| Exact canonical form state | 1.000 | 1.000 |
| Context retention | 0.500 | 1.000 |
| Latest-answer adherence | 0.000 | 1.000 |
| Contradiction failures | 1 | 0 |
| Unnecessary repetition | 0.125 | 0.000 |
| Recovery success | 0.000 | 1.000 |
| Heuristic naturalness | 4.708/5 | 5.000/5 |
| Deterministic failures | 14 | 0 |
| Qualitative failure reasons | 10 | 0 |
| Invention failures | 0 | 0 |

The comparison found 14 fixed deterministic failures, no new failures, and no
unchanged failures. The final run took longer on average because an unsafe
first explanation may consume the existing single model correction retry.
Deterministic spoken-number and dropdown turns do not add model calls.

Generated evidence remains local and ignored by Git:

- `backend/evaluations/results/20261013205409597815-milestone-7-4-baseline-live.json`
- `backend/evaluations/results/20261013210057636393-milestone-7-4-candidate-final.json`
- `backend/evaluations/results/milestone-7.4-final-comparison.json`

## Unchanged-suite regression

The completed Milestone 7.2 suite remained on its original digest. All 47 turns
completed with exact form-state accuracy `0.875`, context retention `1.000`,
recovery `0.857`, zero repetition, and zero invention. Its only deterministic
failures remain the three previously recorded occupancy-date presentation
mismatches; no new failure identity appeared.

## Commands

From `backend`, with the virtual environment active and `.env` exported:

```bash
python -m evaluations.conversation_harness run \
  --label milestone-7.4-candidate \
  --scenarios evaluations/scenarios/voice_interview_reliability.json \
  --judge

python -m evaluations.conversation_harness compare \
  evaluations/results/BASELINE.json \
  evaluations/results/CANDIDATE.json \
  --output evaluations/results/milestone-7.4-comparison.json
```

The production Form Agent still owns no persistence, makes no PDF calls, and
cannot confirm a value from assistant wording. Every interpreted answer remains
a typed proposal until a separate validated confirmation event is received.
