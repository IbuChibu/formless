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
Nebius Token Factory, Tavily, or Deepgram is configured; provider configuration
is checked when the corresponding assistant feature is used. Manual PDF
extraction, editing, filling, and download remain available if a provider is
unavailable.

For voice input, add a Deepgram key with Member permission to `backend/.env`:

```env
DEEPGRAM_API_KEY=your_server_side_key
DEEPGRAM_BASE_URL=https://api.deepgram.com/v1
```

Never put this key in a `VITE_` variable. FastAPI exchanges it for a temporary
browser credential only when a user explicitly starts listening.

Voice input uses Deepgram Nova-3 streaming and requires a browser with
`getUserMedia`, `MediaRecorder`, and WebSocket support on `localhost` or HTTPS.
After uploading a form, select **Start conversation** once. The assistant reads
the visible question and temporarily analyses local microphone levels while
speaking. Start talking to interrupt it hands-free, or use **Answer now**;
either route opens the same one-turn recognizer. Interim words remain visibly
labelled, and only one finalized utterance enters the same Form Agent path as
typed text. `window.SpeechRecognition` is not required.

Formless does not retain audio, temporary tokens, or word-confidence metadata.
Streaming requests set `mip_opt_out=true`; according to Deepgram's
[data-handling documentation](https://developers.deepgram.com/trust-security/your-data),
opted-out audio and transcripts are retained only as needed to process the
request, while non-content request metadata and usage logs are still recorded.
A proposal still changes nothing until explicitly confirmed. **Pause** and
**End** release microphone and socket resources without changing the form.
Typing and visible proposal controls remain available when voice is
unconfigured, unsupported, denied, disconnected, or uncertain.

## Checks

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
python -m evaluations.form_agent_transcript_evaluation

cd ../frontend
npm run test:workspace-layout
npm run test:voice-interruption
npm run test:deepgram-speech
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
