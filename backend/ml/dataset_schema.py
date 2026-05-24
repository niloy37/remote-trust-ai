from __future__ import annotations

CLASSIFICATION_LABELS = [
    "LEGIT_REMOTE",
    "COUNTRY_RESTRICTED_REMOTE",
    "HYBRID_OR_LOCATION_BOUND",
    "LOW_QUALITY_UNVERIFIED",
    "LIKELY_SCAM",
]

REQUIRED_DATASET_COLUMNS = ["id", "text", "label", "split"]

RECOMMENDED_DATASET_COLUMNS = [
    "source_url",
    "company",
    "job_title",
    "applicant_country",
    "structured_features_json",
    "graph_evidence_json",
    "review_notes",
]

DATASET_COLUMNS = [*REQUIRED_DATASET_COLUMNS, *RECOMMENDED_DATASET_COLUMNS]
