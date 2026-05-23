# RemoteTrust AI Pipeline

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

## 1. Job Sources / User Input

The MVP accepts either a job URL or pasted job description. If only a URL is provided, the backend attempts a lightweight HTML fetch and text cleanup. For demo reliability, pasted descriptions are the primary path.

## 2. Preprocessing

The backend normalizes whitespace, strips basic HTML, and passes text into the local ML package.

## 3. Feature Extraction

`ml/feature_extractor.py` extracts:

- company name
- job title
- salary
- location
- remote type
- allowed countries
- timezone requirements
- work authorization requirements
- suspicious contact methods
- scam phrases
- apply URL
- required skills
- seniority level

## 4. Scoring

`ml/scorer.py` computes four pillar scores:

- Legitimacy
- Remote Authenticity
- Global Eligibility
- Job Quality

The final score is a weighted average:

```text
40% legitimacy + 25% remote authenticity + 20% global eligibility + 15% job quality
```

## 5. Storage and Feedback

The FastAPI backend stores the job analysis and user feedback in SQLite. The schema is intentionally simple and can be migrated to PostgreSQL later.

## 6. Advanced Classification MVP

The backend produces an additive advanced classification result with one of five
labels: `LEGIT_REMOTE`, `COUNTRY_RESTRICTED_REMOTE`,
`HYBRID_OR_LOCATION_BOUND`, `LOW_QUALITY_UNVERIFIED`, or `LIKELY_SCAM`.

The MVP uses local deterministic evidence from the existing scorer, extracted
remote restrictions, graph trust score when available, red flags, and positive
signals. Optional transformer and structured ML artifacts are not required for
local operation; when absent, their layer statuses are reported as unavailable.

## 7. Future ML

`ml/train_baseline.py` trains a TF-IDF + Logistic Regression classifier. `ml/finetune_transformer.py` documents a future Hugging Face fine-tuning path once there is a larger labeled dataset.
