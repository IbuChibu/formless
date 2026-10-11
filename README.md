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
