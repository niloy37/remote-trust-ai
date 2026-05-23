from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import AnalyzeRequest
from app.services.analyzer import analyze


def test_analyze_response_has_additive_classification_fields() -> None:
    response = analyze(
        AnalyzeRequest(
            applicant_country="Canada",
            job_description="""
            Company: ExampleCloud
            Job title: Backend Engineer
            Fully remote. Global applicants welcome.
            Responsibilities include building APIs and collaborating with teams.
            Required skills: Python, FastAPI, SQL. Salary: $100,000 to $130,000.
            """,
        )
    )
    payload = response.model_dump()

    assert "final_score" in payload
    assert "verdict" in payload
    assert "scores" in payload
    assert "classification" in payload
    classification = payload["classification"]
    assert classification["label"]
    assert 0 <= classification["confidence"] <= 1
    assert classification["evidence"]["top_red_flags"]
    assert classification["evidence"]["positive_signals"]
    assert "remote_restrictions" in classification["evidence"]
    assert "rules" in classification["layer_scores"]
    assert "transformer" in classification["layer_scores"]


def test_sparse_evidence_gets_insufficient_reason_or_flag() -> None:
    response = analyze(
        AnalyzeRequest(
            applicant_country="Canada",
            job_description="Remote job. Flexible work.",
        )
    )

    evidence = response.classification.evidence
    assert evidence.explanation
    assert evidence.top_red_flags or evidence.confidence_factors
