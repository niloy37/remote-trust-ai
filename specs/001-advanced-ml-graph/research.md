# Research: Advanced ML Graph Verification

## Decision: Keep the existing rule scorer as the required local fallback

**Rationale**: The constitution requires RemoteTrust AI to remain useful without
paid APIs, live LLM calls, Neo4j, or advanced artifacts. The current analyzer and
`ml.scorer` already provide deterministic scores, extracted fields, red flags,
positive signals, and recommendations.

**Alternatives considered**: Replacing the current scorer entirely was rejected
because it would make startup and demos dependent on new artifacts. Blocking
analysis when artifacts are missing was rejected because it violates local-first
operation.

## Decision: Add the five-category classifier as an additive result

**Rationale**: Existing clients use `final_score`, `verdict`, `scores`,
`red_flags`, and `positive_signals`. The new classification label, confidence,
layer scores, and evidence should be additive to preserve dashboard, saved job,
and feedback flows.

**Alternatives considered**: Replacing `verdict` with the new enum was rejected
because it would break existing UI and persisted records. Mapping the five labels
only to existing `Verified/Caution/Risky` was rejected because it loses the
country-restricted and hybrid/location-bound distinctions.

## Decision: Use a layered local classifier contract

**Rationale**: The requested pipeline has semantic text classification,
structured ML probability, rule score, graph trust score, and a meta-classifier.
Each layer will return probabilities, status, evidence, and missing-artifact
reasons. The meta-classifier combines available layers and records skipped layers.

**Alternatives considered**: A monolithic model was rejected because it cannot
explain which layer contributed evidence. Hard-coded rules only were rejected
because the feature asks for ML training and evaluation workflows.

## Decision: Treat transformer support as optional local artifact support

**Rationale**: Transformer inference can be heavy and may require packages or
artifacts not currently installed. The baseline must not require network downloads
or paid calls. The transformer layer should load local artifacts when present and
return `unavailable` when absent.

**Alternatives considered**: Downloading a model at runtime was rejected because
network availability is not guaranteed and would undermine reproducible local
demos. Making transformer packages mandatory was rejected for MVP stability.

## Decision: Use scikit-learn/joblib for structured and meta-classifier baselines

**Rationale**: The project already uses scikit-learn and joblib for local model
training. Gradient boosting and simple meta-classification can be implemented
within the existing dependency style and saved under `ml/artifacts/`.

**Alternatives considered**: Adding a new heavy ML framework was rejected because
it increases setup cost without being necessary for the baseline. Using only
logistic regression was rejected because the user explicitly requested gradient
boosting for structured features.

## Decision: Expand graph verification around current GraphVerification patterns

**Rationale**: The backend already has `GraphVerification` response data and
SQLite graph tables. The new graph layer should add relationship statuses for
company, domain, recruiter email, ATS provider, job source, country restrictions,
and apply URL while preserving the existing status/score/evidence shape.

**Alternatives considered**: Creating a separate graph-only API was rejected
because users need graph evidence inside the analysis result. Requiring Neo4j was
rejected because SQLite fallback is required for local-first behavior.

## Decision: Store advanced classification JSON additively

**Rationale**: SQLite migrations can add nullable JSON columns for advanced
classification and layer evidence. Older records can synthesize a degraded
classification view from existing scores and warnings.

**Alternatives considered**: Rebuilding the `jobs` table was rejected as risky for
existing saved analyses. Storing only flattened columns was rejected because layer
evidence evolves and includes nested lists.

## Decision: Document dataset format as CSV-first with JSON fields where needed

**Rationale**: The current project uses CSV sample labeled data. A CSV format with
structured JSON string fields for graph and restriction evidence is easy to edit
locally and can be validated by training scripts.

**Alternatives considered**: A database-only training source was rejected because
it is harder to review and version. JSONL was considered but CSV better matches
the existing sample workflow.
