# Milestone 9.1.1 natural-language interpretation comparison

Recorded: 19 October 2026

Suite: `natural-language-turn-interpretation-v1`

Suite digest: `13246da029a1a841`

Pre-change Git revision: `cc61298`

Model: `nvidia/Nemotron-3_5-Lightning`

The pre-change code was exported from Git into a temporary directory and run
against the exact candidate scenario file. The harness confirmed that both
reports used the same suite digest before producing the comparison.

Command shape:

```bash
cd backend
set -a
source .env
set +a
PYTHONPATH=. .venv/bin/python -m evaluations.conversation_harness run \
  --scenarios evaluations/scenarios/natural_language_turn_interpretation.json \
  --label <baseline-or-candidate-label>
```

## Fixed coverage

- 19 scenarios and 40 scheduled candidate turns
- names and free text
- spoken-style dates and numbers
- positive and negative checkbox paraphrases
- ordinary-language dropdown descriptions
- uncertainty and explanation requests
- conversational skip and return-to-field navigation
- a correction that preserves the confirmed value
- two facts supplied in one turn and later recalled
- an unrelated interruption that must not become a fact or preference

All personal information is synthetic. Factual candidates remain proposals
until an explicit confirmation event.

## Before and after

| Metric | Pre-change baseline | Candidate |
| --- | ---: | ---: |
| Completed-turn rate | 0.950 | 1.000 |
| Form-state accuracy | 0.895 | 1.000 |
| Context retention | 0.500 | 1.000 |
| Latest-answer adherence | 0.286 | 1.000 |
| Recovery success | 0.000 | 1.000 |
| Interruption recovery | 0.000 | 1.000 |
| Deterministic failures | 34 | 0 |
| Unnecessary repetition | 0.000 | 0.000 |
| Invention failures | 0 | 0 |
| Contradiction failures | 0 | 0 |
| Confirmation-boundary failures | 0 | 0 |
| Average turn latency | 142.886 ms | 340.122 ms |

The digest-checked comparison reported 34 fixed failures, no new failures, and
no unchanged failures. Average latency increased by 197.236 ms on this focused
model-handled suite; the deterministic fast paths still avoid a model call.

## Result

The candidate correctness gate passed. Equivalent natural answers produced the
expected prepared values, while uncertainty, unrelated conversation, and
ungrounded preference interpretations remained non-factual. Every accepted
fact was still only a proposal, multi-field memory stayed bounded, and a
replacement proposal left the previously confirmed value intact.

The generated JSON and Markdown reports remain in the ignored local
`backend/evaluations/results` directory. The pre-change report was generated
from the archived revision in a temporary directory and then copied into that
results directory. This tracked comparison retains the reproducible digest,
revision, commands, and metrics.
