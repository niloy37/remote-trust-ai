# RemoteTrust AI

RemoteTrust AI is a hackathon MVP for verifying whether remote job postings are legitimate, actually remote, globally eligible, and high quality. It runs locally end-to-end with a Next.js frontend, FastAPI backend, SQLite database, optional Neo4j relationship graph, and a hybrid AI scoring engine that works without paid APIs.

## Architecture

```text
remote-trust-ai/
  frontend/     Next.js App Router + TypeScript + Tailwind dashboard UI
  backend/      FastAPI REST API + SQLite persistence + graph fallback
  ml/           Feature extraction, rule scorer, baseline ML scripts
  data/         Sample job postings for demo seeding
  docs/         Pipeline, pitch, and demo script
```

## Pipeline

```text
Job Sources / User Input
↓
Job Description Extraction
↓
Preprocessing
↓
Feature Extraction
↓
Legitimacy + Remote + Eligibility + Quality Scoring
↓
Final Trust Score
↓
Dashboard + Feedback Loop
↓
Future Model Fine-Tuning
```

## Local Setup

### Backend

```bash
cd remote-trust-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs are available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Seed Sample Data

```bash
cd remote-trust-ai/backend
python seed_db.py --reset
```

This analyzes the eight sample postings in `data/sample_jobs.json` and stores them in SQLite.

### Frontend

```bash
cd remote-trust-ai/frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API Endpoints

- `GET /health` returns service and database status.
- `POST /analyze` analyzes a job URL or pasted job description.
- `GET /jobs` lists analyzed jobs.
- `GET /jobs/{job_id}` returns a saved analysis.
- `POST /feedback` stores applicant feedback.

## URL Crawling

The backend includes a lightweight crawler for URL-only analysis. It works best on public company career pages and ATS links such as Greenhouse, Lever, Ashby, Workable, and SmartRecruiters. It tries structured `JobPosting` JSON-LD first, then cleaned page text and metadata.

LinkedIn and Indeed commonly hide job content behind login, bot checks, or dynamic rendering. The MVP attempts public extraction, but if the page blocks useful content it returns a clear fallback asking the user to paste the description. A future browser extension can read those pages with user consent from the active browser session.

## Scoring

Final score:

```text
40% legitimacy
25% remote authenticity
20% global eligibility
15% job quality
```

Verdicts:

```text
80-100  Verified
60-79   Caution
0-59    Risky
```

RemoteTrust AI also returns a local `title_validation` object that checks whether the extracted job title looks like a credible occupation. It uses local taxonomy-style aliases, fuzzy matching, title-description consistency, and scam/buzzword heuristics. No paid API or live LLM call is required.

The API also returns an additive `classification` object for the advanced MVP
classifier. It maps each posting to `LEGIT_REMOTE`,
`COUNTRY_RESTRICTED_REMOTE`, `HYBRID_OR_LOCATION_BOUND`,
`LOW_QUALITY_UNVERIFIED`, or `LIKELY_SCAM`, with confidence, layer status,
remote restriction evidence, red flags, and positive signals. The MVP path is
local-first: missing transformer or structured ML artifacts are reported as
unavailable and the deterministic rule fallback still returns a classification.

The API also returns `company_verification`, a live web-evidence object that searches for official company pages, public company profiles, employee/company review pages, and scam/fraud warning language. It is free and server-side by default, with graceful fallback to `Limited evidence` when public search is blocked.

The backend also runs an internal graph verification layer. In Docker it uses Neo4j to connect companies, jobs, domains, recruiter contacts, ATS platforms, review sources, source pages, and risk signals. If Neo4j is unavailable, it falls back to SQLite graph tables. The frontend does not show a separate graph widget; graph-derived evidence is folded into the existing scores, explanation, red flags, positive signals, and company verification messaging.

## Baseline ML Training

The MVP does not require a model to run, but the baseline script demonstrates the next ML step.

```bash
cd remote-trust-ai
python -m ml.train_baseline
python -m ml.evaluate
```

The script trains a TF-IDF + Logistic Regression classifier on `ml/sample_labeled_jobs.csv` and saves `ml/artifacts/baseline_model.joblib`.

## Docker Compose

```bash
cd remote-trust-ai
docker compose up --build
```

Then visit [http://localhost:3000](http://localhost:3000). The backend runs on [http://localhost:8000](http://localhost:8000). Neo4j Browser is available at [http://localhost:7474](http://localhost:7474) with the local demo credentials from `docker-compose.yml`.

## Chrome Extension

A standalone Chrome extension is included in `chrome-extension/`. It reads LinkedIn and Indeed job pages only after the user confirms consent in the popup, then sends the extracted job description to the local backend.

Load it from Chrome:

```text
chrome://extensions -> Developer mode -> Load unpacked -> remote-trust-ai/chrome-extension
```

Keep the backend running at `http://127.0.0.1:8000`.

## Environment Variables

Backend:

```text
SQLITE_PATH=remote_trust.db
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
OPENAI_API_KEY=optional_future_extension
WEB_VERIFICATION_ENABLED=true
WEB_SEARCH_TIMEOUT_SECONDS=5
WEB_SEARCH_MAX_RESULTS=7
GRAPH_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=remote-trust-dev
```

Frontend:

```text
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_PATH=/api/backend
```

OpenAI or external LLM usage is intentionally optional. The local scoring engine works without paid APIs.

## Demo Flow

1. Start backend and frontend.
2. Seed sample data.
3. Open the landing page and click **Analyze a Job**.
4. Try **Verified Example**, **Scam Example**, and **Restricted Remote Example**.
5. Open the dashboard and filter by verdict or country.
6. Submit feedback from a results panel to show the feedback loop.
