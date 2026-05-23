# Data Model: Advanced ML Graph Verification

## JobClassification

Represents the final five-category prediction for an analyzed job.

**Fields**:

- `label`: enum, one of `LEGIT_REMOTE`, `COUNTRY_RESTRICTED_REMOTE`,
  `HYBRID_OR_LOCATION_BOUND`, `LOW_QUALITY_UNVERIFIED`, `LIKELY_SCAM`.
- `confidence`: number from 0.0 to 1.0.
- `recommendation`: enum/string compatible with current user guidance.
- `layer_scores`: `LayerScores`.
- `evidence`: `ClassificationEvidence`.
- `status`: enum `complete`, `degraded`, `fallback`.
- `fallback_reason`: optional string.

**Validation Rules**:

- `label` is required for every completed analysis.
- `confidence` must be clamped between 0.0 and 1.0.
- `status=fallback` requires `fallback_reason`.
- Evidence must contain at least one explanation item or an explicit
  insufficient-evidence message.

## LayerScores

Captures probability and availability for each classifier layer.

**Fields**:

- `transformer`: `LayerScore`.
- `structured_ml`: `LayerScore`.
- `rules`: `LayerScore`.
- `graph`: `LayerScore`.
- `meta`: `LayerScore`.

## LayerScore

**Fields**:

- `status`: enum `available`, `skipped`, `unavailable`, `degraded`.
- `probabilities`: map of classification label to number from 0.0 to 1.0.
- `score`: optional number from 0.0 to 1.0 for single-score layers.
- `evidence`: list of strings.
- `reason`: optional string explaining skipped/unavailable/degraded status.

**Validation Rules**:

- Available probability layers must include all five labels.
- Probabilities must be normalized or clearly marked as rule-derived scores.
- Unavailable or skipped layers must include `reason`.

## ClassificationEvidence

Ranks the evidence shown to users and maintainers.

**Fields**:

- `top_red_flags`: list of strings.
- `positive_signals`: list of strings.
- `remote_restrictions`: `RemoteRestrictionEvidence`.
- `graph_summary`: `GraphVerificationResult`.
- `confidence_factors`: list of strings.
- `explanation`: string.

**Validation Rules**:

- At least one of red flags, positive signals, remote restrictions, graph
  summary, or confidence factors must explain the final label.
- Evidence strings must not include secrets or raw credentials.

## RemoteRestrictionEvidence

Represents extracted location, eligibility, and work-mode constraints.

**Fields**:

- `allowed_countries`: list of strings.
- `excluded_countries`: list of strings.
- `timezone_requirements`: optional string.
- `work_authorization`: optional string.
- `onsite_or_hybrid_requirement`: optional string.
- `ambiguous_location_language`: list of strings.
- `source_snippets`: list of strings.

**Validation Rules**:

- Source snippets must be short excerpts sufficient for explanation.
- Country-restricted labels require at least one country, authorization, timezone,
  or source-snippet restriction.

## GraphVerificationResult

Extends the existing graph evidence into relationship-specific results.

**Fields**:

- `status`: enum `strong_support`, `some_support`, `limited_evidence`,
  `conflict`, `unavailable`.
- `score`: integer 0-100.
- `entity_confidence`: integer 0-100.
- `relationships`: list of `GraphRelationshipEvidence`.
- `signals`: list of strings.
- `warnings`: list of strings.
- `evidence_paths`: list of strings.
- `fallback_backend`: enum `neo4j`, `sqlite`, `none`.

**Validation Rules**:

- `unavailable` requires a reason in warnings.
- Conflicting recruiter/domain/apply URL evidence must appear in warnings.

## GraphRelationshipEvidence

**Fields**:

- `source_kind`: company, domain, recruiter_email, ats_provider, job_source,
  country_restriction, apply_url.
- `source_value`: string.
- `target_kind`: same allowed set.
- `target_value`: string.
- `relationship_type`: string, such as `USES_DOMAIN`, `POSTED_ON`,
  `CONTACTED_BY`, `RESTRICTED_TO`, `APPLY_URL_MATCHES`.
- `status`: enum `supports`, `conflicts`, `unknown`.
- `evidence`: optional string.

## StructuredFeatureRecord

Normalized feature vector source used for structured ML and training validation.

**Fields**:

- `job_text`: string.
- `job_title`, `company`, `location`, `remote_type`, `salary`: optional strings.
- `allowed_countries`, `excluded_countries`, `skills`, `contact_methods`: lists.
- `has_suspicious_contact`, `has_payment_request`, `has_salary`, `has_apply_url`:
  booleans.
- `company_verification_score`, `graph_trust_score`, `rule_score`: numeric.
- `source_type`, `ats_provider`, `recruiter_email_domain`, `apply_domain`:
  optional strings.

## LabeledTrainingExample

Training row for advanced classification workflows.

**Fields**:

- `id`: stable string.
- `text`: raw job text.
- `label`: one of the five classification labels.
- `split`: enum `train`, `validation`, `test`.
- `source_url`, `company`, `job_title`, `applicant_country`: optional strings.
- `structured_features_json`: optional JSON object.
- `graph_evidence_json`: optional JSON object.
- `review_notes`: optional string.

**Validation Rules**:

- `id`, `text`, `label`, and `split` are required.
- Label must be one of the five categories.
- Dataset validation must report class counts and fail on unknown labels.

## EvaluationReport

Maintainer-facing output for model quality review.

**Fields**:

- `dataset_path`: string.
- `created_at`: ISO timestamp.
- `class_distribution`: map of label to count.
- `metrics_by_label`: precision, recall, F1, and support per label.
- `confusion_matrix`: matrix with labels in deterministic order.
- `misclassified_examples`: list of IDs with expected/actual labels and short
  notes.

## State Transitions

```text
raw input
  -> extracted features
  -> layer predictions
  -> graph verification
  -> meta-classification
  -> persisted job analysis
  -> feedback/evaluation loop
```

Fallback transition:

```text
raw input
  -> existing extraction/rule scoring
  -> fallback classification view
  -> persisted job analysis with degraded layer statuses
```
