# Formless

Formless is a conversation-first assistant for understanding and completing
fillable PDF forms. The React frontend keeps the PDF and confirmed field state;
the FastAPI backend keeps PDF manipulation separate from the Nemotron-powered
Form Agent.

## Run locally

Backend, from the repository root:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
set -a
source .env
set +a
uvicorn app.main:app --reload
```

Copy `backend/.env.example` to `backend/.env` first if needed, then add your
server-side credentials. Do not commit `backend/.env`.

Frontend, in a second terminal from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The header reports only whether the FastAPI
backend is reachable. A successful `GET /health` response does not prove that
Nebius Token Factory or Tavily is configured; provider configuration is checked
when the corresponding assistant feature is used. Manual PDF extraction,
editing, filling, and download remain available if an AI provider is
unavailable.

Voice input uses the browser's speech-recognition capability and therefore
requires a supported browser on `localhost` or HTTPS. After uploading a form,
select **Start conversation** once. The assistant reads the visible question,
listens for one answer, displays the transcript, and sends it through the same
Form Agent path as typed text. A proposal still changes nothing until it is
explicitly confirmed; while its review card is visible, phrases such as
`confirm that`, `put that in`, `no`, and `skip this` use the same validated
events as the buttons. **Pause** and **End** stop microphone capture and spoken
output without changing the form. Typing and visible proposal controls remain
available when voice is unsupported, denied, interrupted, or misheard.

## Checks

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
python -m evaluations.form_agent_transcript_evaluation

cd ../frontend
npm run build
```

The optional live conversation-quality evaluation uses the credentials loaded
from `backend/.env`:

```bash
cd backend
source .venv/bin/activate
set -a
source .env
set +a
python -m evaluations.form_agent_conversation_quality
```

Milestone 6.14 compares the configured primary model with one stronger
Token Factory candidate using the same fixed scenarios. Add an available model
ID to `NEBIUS_CANDIDATE_MODEL` in `backend/.env`, then run:

```bash
cd backend
source .venv/bin/activate
set -a
source .env
set +a
python -m evaluations.form_agent_model_selection
```

The models are evaluated sequentially. The JSON report contains no credentials
and includes both metric sets, side-by-side scenario messages, latency, model
calls, metric deltas, and a deterministic recommendation. This command does not
change the production model; `NEBIUS_MODEL` remains the single runtime model.

The recorded Milestone 6.14 comparison used
`nvidia/Nemotron-3-Ultra-550b-a55b` as the candidate and retained Lightning: the
candidate regressed guided conversation-repair metrics and was 4.419 times
slower on the fixed live scenarios.

## Conversation evaluation harness

Milestone 7.2 adds an evaluation-only lab for realistic complete interviews.
Eight fixed synthetic personas exercise bundled answers, corrections,
ambiguity, field questions, interruptions, skips, frustration, and returning to
earlier fields. The simulator uses schemas extracted from the checked-in PDF
fixtures and calls the same Form Agent application boundary as the UI.

Run the full live suite and add the optional Nemotron qualitative rubric:

```bash
cd backend
source .venv/bin/activate
set -a
source .env
set +a
python -m evaluations.conversation_harness run --label baseline --judge
```

The command prints summary metrics and writes a full JSON report plus a readable
Markdown transcript to `backend/evaluations/results/`. Generated reports are
ignored by Git. They include no credentials and use synthetic personal
information only.

To exercise the exact HTTP interface instead, start FastAPI and run:

```bash
cd backend
source .venv/bin/activate
python -m evaluations.conversation_harness run \
  --label api-baseline \
  --target http \
  --base-url http://127.0.0.1:8000
```

After a targeted change, rerun with a new label and compare the two printed JSON
paths:

```bash
cd backend
source .venv/bin/activate
python -m evaluations.conversation_harness compare \
  evaluations/results/BASELINE_REPORT.json \
  evaluations/results/CANDIDATE_REPORT.json \
  --output evaluations/results/comparison.json
```

Comparison requires the same scenario-suite digest. It reports metric deltas
and stable fixed, new, and unchanged deterministic failures so changing
qualitative wording does not disguise a form-state regression. The checked
Milestone 7.2 baseline and its largest observed weaknesses are summarized in
[`docs/milestone-7.2-conversation-evaluation-baseline.md`](docs/milestone-7.2-conversation-evaluation-baseline.md).
The accepted Milestone 7.3 comparison and its one conservative residual format
difference are summarized in
[`docs/milestone-7.3-conversation-reliability-result.md`](docs/milestone-7.3-conversation-reliability-result.md).

Milestone 7.4 adds a smaller voice-like reliability suite with deterministic
checks for the newest short answer, contradictory response wording, safe
finite-choice near matches, unsupported date advice, and edited-confirmation
visibility. Run it with:

```bash
cd backend
source .venv/bin/activate
set -a
source .env
set +a
python -m evaluations.conversation_harness run \
  --label voice-reliability \
  --scenarios evaluations/scenarios/voice_interview_reliability.json \
  --judge
```

The accepted same-digest result is summarized in
[`docs/milestone-7.4-voice-conversation-reliability-result.md`](docs/milestone-7.4-voice-conversation-reliability-result.md).
