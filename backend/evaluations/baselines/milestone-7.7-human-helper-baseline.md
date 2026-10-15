# Milestone 7.7 human-helper baseline

Recorded: 15 October 2026

Suite: `human-helper-experience-v1`

Suite digest: `2529802e73125ede`

Target: in-process `FormAgentService`

Model: `nvidia/Nemotron-3_5-Lightning`

This checked-in summary contains synthetic evaluation data only. The complete
JSON and Markdown transcript artifacts remain local and ignored under
`backend/evaluations/results`.

## Command

From `backend`, after loading the local `.env` into the shell:

```bash
PYTHONPATH=. .venv/bin/python -m evaluations.conversation_harness run \
  --scenarios evaluations/scenarios/human_helper_experience.json \
  --label milestone-7-7-baseline
```

## Baseline metrics

- scheduled scenarios: 14
- scheduled turns: 182
- recorded turns before stopped paths: 144
- completed-turn rate: 0.747
- exact form-state accuracy: 0.572
- legacy context-retention metric: not scored in this suite
- unnecessary adjacent-response repetition: 0.104
- heuristic naturalness: 4.314/5
- volunteered-fact recall: not reached on the stopped bundled-answer paths
- side-question recovery: 0.433
- unnecessary-push rate: 0.442
- speech suitability: 1.000
- acknowledgement: 0.708
- interruption recovery: 0.834
- clarification success: 0.500
- overall observed human-helper behaviour: 0.812
- scheduled behaviour-check coverage: 0.730
- turns per confirmed field: 4.500
- invention failures: 0
- confirmation-boundary failures: 0
- correctness gate: failed
- human-helper gate: failed

The optional qualitative judge was not enabled for this baseline. The
deterministic transcript and form-state evidence remains authoritative.

## Main observed weaknesses

1. A message containing a legal name plus a date and housing arrangement was
   treated as an ambiguous name instead of extracting the active answer and
   retaining the volunteered facts. The scripted conversation then stopped at
   the now-invalid confirmation event.
2. Short-text values sometimes retained conversational framing or terminal
   punctuation, including `Okafor.` and `I am back. It is J.`.
3. Several post-completion questions returned the generic completed-form
   message instead of answering whether anything was skipped or unanswered,
   returning a requested stored value, or starting a requested correction.
4. A relevant side question such as whether a person living alone counts
   themselves was misclassified as an unmatched field reference.
5. Side-question recovery and acknowledgement were inconsistent even when
   state safety was preserved.
6. Failed interpretation paths often left the following fixed confirmation
   invalid. This is visible through partial transcripts and behaviour-check
   coverage rather than being silently omitted.

## Safety result

No evaluated proposal or claim was marked as invented, and the simulator
observed no write to confirmed form state without an explicit `confirm` or
`confirm_edit` event. These safety results do not compensate for incomplete or
unhelpful conversations.

## Comparison policy

Future candidates must run this exact suite digest. Use the deterministic
comparison first:

```bash
PYTHONPATH=. .venv/bin/python -m evaluations.conversation_harness compare \
  BASELINE.json CANDIDATE.json --output comparison.json
```

An optional label-blinded qualitative comparison can then be run with the
configured Nemotron credentials:

```bash
PYTHONPATH=. .venv/bin/python -m evaluations.conversation_harness pairwise \
  BASELINE.json CANDIDATE.json --output pairwise.json
```
