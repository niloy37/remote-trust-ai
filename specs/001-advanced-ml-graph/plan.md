# Implementation Plan: Advanced ML Graph Verification

**Branch**: `001-advanced-ml-graph` | **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-advanced-ml-graph/spec.md`

## Summary

Extend RemoteTrust AI from a numeric trust verdict into a five-category
classification system with explainable evidence. The implementation will add an
advanced local ML classification layer, structured feature extraction, graph
verification scoring, model training/evaluation workflows, additive API response
fields, and tests while preserving the current rule-based local fallback.

## Technical Context

**Language/Version**: Python 3.12 backend/ML, TypeScript with Next.js App Router
frontend

**Primary Dependencies**: FastAPI, Pydantic v2, SQLite, scikit-learn, joblib,
Neo4j Python driver, Next.js, Tailwind. Optional transformer support will be
isolated behind local artifacts and disabled gracefully when unavailable.

**Storage**: SQLite for saved analyses, feedback, and fallback graph tables;
optional Neo4j for relationship graph verification; filesystem artifacts under
`ml/artifacts/` for trained models and evaluation output.

**Testing**: Backend and ML tests with pytest; frontend user-path verification
with existing Next.js tooling where available; manual quickstart validation for
local fallback and optional Neo4j behavior.

**Target Platform**: Local developer/demo environment, Docker Compose, browser
frontend, FastAPI backend, and local ML scripts.

**Project Type**: Web application with backend API, frontend dashboard, local ML
package, optional graph service, and Chrome extension compatibility.

**Performance Goals**: A local analysis with available artifacts should complete
in a user-acceptable interactive flow; graph and external verification timeouts
must not block fallback classification. Training/evaluation workflows are
maintainer-facing and may run longer than request-time analysis.

**Constraints**: No paid API or live LLM is required for baseline operation.
Neo4j, external verification, transformer artifacts, and advanced model artifacts
must be optional with explicit skipped/unavailable/degraded statuses.

**Scale/Scope**: One feature slice covering the five classification labels,
explainable evidence, graph verification expansion, training/evaluation scripts,
sample dataset format, additive API response updates, backend integration, and
tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Local-first trust scoring**: PASS. The plan keeps existing rule-based and
  local ML scoring as the baseline. Advanced model artifacts, transformer
  artifacts, Neo4j, and external verification are optional and degrade with
  explicit statuses.
- **Evidence traceability**: PASS. The plan requires layer scores, confidence,
  red flags, positive signals, remote restrictions, graph relationships, and
  skipped/unavailable reasons in analysis responses and saved records.
- **Testable user-slice delivery**: PASS. The primary slice is `/analyze` returning
  one of five categories with evidence; secondary slices cover graph verification
  and maintainer training/evaluation. Tests target classification, evidence
  completeness, fallbacks, graph outcomes, dataset validation, and reporting.
- **Privacy and consent**: PASS. The plan stores only analysis evidence already
  derived from user-provided job text/URLs and explicitly excludes secrets from
  datasets, artifacts, graph seed data, logs, and API responses.
- **Resilient integrations**: PASS. Neo4j, web verification, URL crawling,
  transformer artifacts, and advanced model artifacts must return clear degraded
  statuses and fall back to local rule/ML scoring.

## Project Structure

### Documentation (this feature)

```text
specs/001-advanced-ml-graph/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- api-openapi.yaml
|   `-- dataset-format.md
`-- checklists/
    `-- requirements.md
```

### Source Code (repository root)

```text
backend/
|-- app/
|   |-- api/
|   |   `-- routes.py
|   |-- db/
|   |   `-- database.py
|   |-- models.py
|   `-- services/
|       |-- analyzer.py
|       |-- graph_verifier.py
|       |-- job_fetcher.py
|       `-- web_verifier.py
`-- tests/
    |-- test_advanced_classification.py
    |-- test_analyze_contract.py
    `-- test_graph_fallbacks.py

ml/
|-- advanced_classifier.py
|-- advanced_features.py
|-- dataset_schema.py
|-- evaluate_advanced.py
|-- train_advanced.py
|-- artifacts/
|   `-- generated local model artifacts
`-- tests/
    |-- test_advanced_features.py
    |-- test_dataset_schema.py
    `-- test_evaluate_advanced.py

data/
`-- sample_advanced_jobs.csv

frontend/
|-- components/
|   `-- ResultsPanel.tsx
|-- lib/
|   |-- api.ts
|   `-- types.ts
`-- app/
    |-- analyze/page.tsx
    |-- dashboard/page.tsx
    `-- results/[jobId]/page.tsx

docs/
|-- pipeline.md
`-- quickstart.md or README.md updates
```

**Structure Decision**: Use the existing web application structure. Backend API
and persistence changes stay under `backend/app/`, local model and feature
workflows stay under `ml/`, sample labeled data stays under `data/`, and frontend
types/rendering are additive updates to the current dashboard/result components.

**Affected RemoteTrust Areas**: `frontend/`, `backend/`, `ml/`, `data/`, `docs/`.
`chrome-extension/` is not directly changed in this plan, but backend response
compatibility must preserve extension-submitted analysis requests.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Multiple classification layers | The feature explicitly requires semantic, structured, rule, graph, and meta-classification evidence | A single rule or text model would not satisfy the requested five-layer explainability and graph trust behavior |
| Optional Neo4j plus SQLite fallback | The constitution requires local-first operation and the feature requires Neo4j graph verification | Requiring Neo4j would break local fallback; SQLite-only would not satisfy the requested Neo4j layer |

## Phase 0 Research Summary

See [research.md](research.md). All technical unknowns are resolved with local-first
defaults: optional transformer artifacts, scikit-learn-compatible structured and
meta-classifiers, additive Pydantic response models, SQLite schema migrations, and
Neo4j/fallback graph status handling.

## Phase 1 Design Summary

See [data-model.md](data-model.md), [contracts/api-openapi.yaml](contracts/api-openapi.yaml),
[contracts/dataset-format.md](contracts/dataset-format.md), and [quickstart.md](quickstart.md).

## Constitution Check Re-Review

- **Local-first trust scoring**: PASS after design. Contracts include fallback
  statuses and quickstart verifies operation without Neo4j or paid APIs.
- **Evidence traceability**: PASS after design. Data model includes layer scores,
  graph evidence, remote restrictions, and ranked evidence lists.
- **Testable user-slice delivery**: PASS after design. Quickstart and contracts
  define independently testable analyze, graph, and training/evaluation paths.
- **Privacy and consent**: PASS after design. Dataset and response contracts
  exclude secrets and use user-provided job/source evidence only.
- **Resilient integrations**: PASS after design. Graph, external verification,
  and model layers have explicit `available`, `skipped`, `unavailable`, or
  `degraded` style statuses.
