# Tasks: Advanced ML Graph Verification

**Input**: Design documents from `/specs/001-advanced-ml-graph/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by the feature specification for category assignment, evidence completeness, fallback behavior, graph verification outcomes, dataset validation, and evaluation reporting.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the shared files and sample data needed by all user stories.

- [X] T001 Create advanced ML module placeholders in `ml/advanced_classifier.py`, `ml/advanced_features.py`, `ml/dataset_schema.py`, `ml/train_advanced.py`, and `ml/evaluate_advanced.py`
- [X] T002 Create test directories and empty package markers in `backend/tests/__init__.py` and `ml/tests/__init__.py`
- [X] T003 [P] Create advanced sample dataset skeleton in `data/sample_advanced_jobs.csv` with all columns from `specs/001-advanced-ml-graph/contracts/dataset-format.md`
- [X] T004 [P] Add advanced classification quickstart references to `README.md` and `docs/pipeline.md`
- [X] T005 [P] Document optional advanced artifact paths and no-paid-API baseline expectations in `backend/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared schemas, persistence, and fallback contracts before any user story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add `ClassificationLabel`, `LayerScore`, `ClassificationEvidence`, `RemoteRestrictionEvidence`, and `JobClassification` Pydantic models in `backend/app/models.py`
- [X] T007 Add matching ML dataclasses for advanced classification outputs in `ml/schemas.py`
- [X] T008 Add `classification_json` nullable storage and backward-compatible row hydration in `backend/app/db/database.py`
- [X] T009 Add graph relationship fields `relationships`, `relationship_status`, and `fallback_backend` to `GraphVerification` in `backend/app/models.py`
- [X] T010 Add fallback classification builder that maps existing scores and rule evidence to the five labels in `ml/advanced_classifier.py`
- [X] T011 [P] Add reusable remote restriction extraction helpers in `ml/advanced_features.py`
- [X] T012 [P] Add shared valid label constants and dataset column constants in `ml/dataset_schema.py`
- [X] T013 [P] Add API contract regression test scaffold for additive response fields in `backend/tests/test_analyze_contract.py`

**Checkpoint**: Shared models, persistence, constants, and fallback contracts are ready.

---

## Phase 3: User Story 1 - Classify a Job With Explainable Evidence (Priority: P1)

**Goal**: Return exactly one of the five classification labels with confidence and explainable evidence for every analysis.

**Independent Test**: Submit representative legitimate, country-restricted, and scam postings through `/analyze` and verify category, confidence, evidence, remote restrictions, and existing score fields are present.

### Tests for User Story 1

- [X] T014 [P] [US1] Add category assignment tests for `LEGIT_REMOTE`, `COUNTRY_RESTRICTED_REMOTE`, `HYBRID_OR_LOCATION_BOUND`, `LOW_QUALITY_UNVERIFIED`, and `LIKELY_SCAM` in `backend/tests/test_advanced_classification.py`
- [X] T015 [P] [US1] Add evidence completeness and confidence status tests in `backend/tests/test_analyze_contract.py`
- [X] T016 [P] [US1] Add remote restriction extraction tests for allowed countries, excluded countries, timezone constraints, authorization, and hybrid language in `ml/tests/test_advanced_features.py`
- [X] T017 [P] [US1] Add fallback behavior tests for missing transformer and advanced model artifacts in `backend/tests/test_advanced_classification.py`

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement structured feature extraction from `ExtractedJob`, rule evidence, company verification, and graph score in `ml/advanced_features.py`
- [X] T019 [P] [US1] Implement local artifact loading with unavailable/degraded layer statuses in `ml/advanced_classifier.py`
- [X] T020 [US1] Implement rule, transformer-placeholder, structured-ML, graph, and meta layer combination into `JobClassification` in `ml/advanced_classifier.py`
- [X] T021 [US1] Integrate advanced classification into `analyze()` and response construction in `backend/app/services/analyzer.py`
- [X] T022 [US1] Persist and hydrate `classification_json` for new and older saved jobs in `backend/app/db/database.py`
- [X] T023 [US1] Expose additive `classification` fields on `/analyze` and `/jobs/{job_id}` through `backend/app/models.py` and `backend/app/api/routes.py`
- [X] T024 [US1] Update frontend API types to include classification label, confidence, layer scores, evidence, and remote restrictions in `frontend/lib/types.ts`
- [X] T025 [US1] Render classification label, confidence, top evidence, and remote restrictions in `frontend/components/ResultsPanel.tsx`
- [X] T026 [US1] Ensure analyze, dashboard, and result pages preserve existing score cards while passing new classification data in `frontend/app/analyze/page.tsx`, `frontend/app/dashboard/page.tsx`, and `frontend/app/results/[jobId]/page.tsx`

**Checkpoint**: User Story 1 is independently functional and testable as the MVP.

---

## Phase 4: User Story 2 - Verify Job Evidence Through Relationship Graphs (Priority: P2)

**Goal**: Summarize company, domain, recruiter, ATS, source, restriction, and apply URL relationships without blocking classification.

**Independent Test**: Analyze postings with supporting, conflicting, missing, and unavailable graph evidence and verify graph summary and classification still return.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add graph support, conflict, limited, and unavailable outcome tests in `backend/tests/test_graph_fallbacks.py`
- [ ] T028 [P] [US2] Add recruiter email domain and apply URL mismatch tests in `backend/tests/test_graph_fallbacks.py`
- [ ] T029 [P] [US2] Add API response tests for relationship statuses and fallback backend values in `backend/tests/test_analyze_contract.py`

### Implementation for User Story 2

- [ ] T030 [P] [US2] Extend graph entity extraction for company, domain, recruiter email, ATS provider, job source, country restriction, and apply URL in `backend/app/services/graph_verifier.py`
- [ ] T031 [US2] Add relationship evidence scoring for support, conflict, unknown, and unavailable states in `backend/app/services/graph_verifier.py`
- [ ] T032 [US2] Store expanded graph nodes and edges for SQLite fallback in `backend/app/db/database.py`
- [ ] T033 [US2] Add Neo4j write/read path for expanded graph relationships with SQLite fallback in `backend/app/services/graph_verifier.py`
- [ ] T034 [US2] Feed graph trust score and relationship warnings into advanced classification layer scores in `backend/app/services/analyzer.py`
- [ ] T035 [US2] Render graph relationship summary, fallback backend, signals, warnings, and evidence paths in `frontend/components/ResultsPanel.tsx`

**Checkpoint**: User Story 2 is independently verifiable with Neo4j available and unavailable.

---

## Phase 5: User Story 3 - Train and Evaluate Classification Improvements (Priority: P3)

**Goal**: Provide maintainers with a documented sample dataset, validation, training, evaluation, and artifact workflow.

**Independent Test**: Run dataset validation, training, and evaluation commands against `data/sample_advanced_jobs.csv` and verify artifacts and metrics for all five labels.

### Tests for User Story 3

- [ ] T036 [P] [US3] Add dataset schema validation tests for required columns, valid labels, split values, JSON parsing, and secret-like values in `ml/tests/test_dataset_schema.py`
- [ ] T037 [P] [US3] Add advanced feature vector tests for structured ML inputs in `ml/tests/test_advanced_features.py`
- [ ] T038 [P] [US3] Add evaluation reporting tests for all five labels, confusion matrix, and misclassified examples in `ml/tests/test_evaluate_advanced.py`

### Implementation for User Story 3

- [ ] T039 [P] [US3] Populate `data/sample_advanced_jobs.csv` with representative examples for all five labels and train/validation/test splits
- [ ] T040 [US3] Implement CSV loading, label validation, split validation, JSON column parsing, and class distribution reporting in `ml/dataset_schema.py`
- [ ] T041 [US3] Implement gradient boosting structured classifier training and artifact saving in `ml/train_advanced.py`
- [ ] T042 [US3] Implement meta-classifier training using transformer probability placeholders, structured probability, rule score, and graph trust score in `ml/train_advanced.py`
- [ ] T043 [US3] Implement optional transformer artifact detection and documented unavailable behavior in `ml/train_advanced.py` and `ml/advanced_classifier.py`
- [ ] T044 [US3] Implement evaluation report generation with precision, recall, F1, confusion matrix, class distribution, and misclassified examples in `ml/evaluate_advanced.py`
- [ ] T045 [US3] Update dataset and training documentation in `specs/001-advanced-ml-graph/contracts/dataset-format.md`, `specs/001-advanced-ml-graph/quickstart.md`, and `README.md`

**Checkpoint**: User Story 3 is independently usable by maintainers for local training and evaluation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate compatibility, documentation, and local-first behavior across the whole feature.

- [ ] T046 [P] Run backend tests and record command/results in `specs/001-advanced-ml-graph/quickstart.md`
- [ ] T047 [P] Run ML tests and record command/results in `specs/001-advanced-ml-graph/quickstart.md`
- [ ] T048 [P] Run frontend type/lint checks and record command/results in `specs/001-advanced-ml-graph/quickstart.md`
- [ ] T049 Validate local analysis without Neo4j, advanced artifacts, paid APIs, or live LLM calls and document result in `specs/001-advanced-ml-graph/quickstart.md`
- [ ] T050 Validate optional Neo4j graph path with Docker Compose and document degraded fallback if unavailable in `specs/001-advanced-ml-graph/quickstart.md`
- [ ] T051 Review saved older jobs for backward-compatible hydration in `backend/app/db/database.py`
- [ ] T052 Update demo flow to mention the five-category classifier and graph evidence in `docs/demo_script.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can proceed after US1 model contracts exist; graph UI integration depends on US1 frontend fields.
- **User Story 3 (Phase 5)**: Depends on Foundational and can proceed in parallel with US2 after US1 establishes classification contracts.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: Required MVP; no dependency on US2 or US3.
- **US2**: Enhances graph evidence and graph layer scoring; depends on US1 contracts for classification integration.
- **US3**: Maintainer workflow; depends on US1 label/entity contracts but not on US2 UI completion.

### Within Each User Story

- Tests must be written before implementation tasks in that story.
- Shared models and persistence must be completed before analyzer/API integration.
- Frontend rendering follows backend response model updates.
- Training and evaluation scripts follow dataset schema validation.

## Parallel Opportunities

- Setup documentation and sample dataset skeleton tasks T003-T005 can run in parallel.
- Foundational tasks T011-T013 can run in parallel after T006-T010 are understood.
- US1 tests T014-T017 can run in parallel.
- US1 implementation tasks T018 and T019 can run in parallel before T020.
- US2 tests T027-T029 can run in parallel.
- US3 tests T036-T038 can run in parallel.
- Polish verification tasks T046-T048 can run in parallel.

## Parallel Example: User Story 1

```bash
Task: "T014 [P] [US1] Add category assignment tests in backend/tests/test_advanced_classification.py"
Task: "T015 [P] [US1] Add evidence completeness tests in backend/tests/test_analyze_contract.py"
Task: "T016 [P] [US1] Add remote restriction extraction tests in ml/tests/test_advanced_features.py"
Task: "T017 [P] [US1] Add fallback behavior tests in backend/tests/test_advanced_classification.py"
```

## Parallel Example: User Story 2

```bash
Task: "T027 [P] [US2] Add graph outcome tests in backend/tests/test_graph_fallbacks.py"
Task: "T028 [P] [US2] Add recruiter/apply URL mismatch tests in backend/tests/test_graph_fallbacks.py"
Task: "T029 [P] [US2] Add response contract tests in backend/tests/test_analyze_contract.py"
```

## Parallel Example: User Story 3

```bash
Task: "T036 [P] [US3] Add dataset schema validation tests in ml/tests/test_dataset_schema.py"
Task: "T037 [P] [US3] Add advanced feature vector tests in ml/tests/test_advanced_features.py"
Task: "T038 [P] [US3] Add evaluation reporting tests in ml/tests/test_evaluate_advanced.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1 tasks T014-T026.
3. Validate `/analyze` returns one of five labels, confidence, evidence, remote restrictions, and existing score fields.
4. Stop and demo the MVP classification path before expanding graph and training workflows.

### Incremental Delivery

1. Deliver US1 for user-facing classification.
2. Deliver US2 for expanded relationship graph verification.
3. Deliver US3 for repeatable maintainer training/evaluation.
4. Complete Phase 6 verification and documentation.

### Format Validation

- All executable tasks use `- [ ] T###` checklist format.
- User story tasks include `[US1]`, `[US2]`, or `[US3]`.
- Parallel tasks use `[P]` only when they target different files or independent test scopes.
- Every task description includes an exact file path.
