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


def analyze_text(text: str, country: str = "Canada"):
    return analyze(AnalyzeRequest(job_description=text, applicant_country=country))


def test_classifies_legit_remote_with_evidence() -> None:
    result = analyze_text(
        """
        Company: ExampleCloud
        Job title: Senior Backend Engineer
        Fully remote, work from anywhere. Global applicants welcome.
        Responsibilities include building APIs, collaborating with product, and owning services.
        Required skills: Python, FastAPI, SQL, Docker.
        Salary: $120,000 to $150,000 per year. Interview process includes recruiter screen and technical interview.
        Apply at https://careers.examplecloud.com/jobs/backend-engineer
        """
    )

    assert result.classification.label == "LEGIT_REMOTE"
    assert result.classification.confidence > 0
    assert result.classification.evidence.positive_signals
    assert result.classification.evidence.remote_restrictions.allowed_countries == ["Worldwide"]
    assert result.final_score >= 0
    assert result.verdict in {"Verified", "Caution", "Risky"}


def test_classifies_country_restricted_remote() -> None:
    result = analyze_text(
        """
        Company: NorthRemote
        Job title: Data Analyst
        This is a fully remote role, Canada only. Must be authorized to work in Canada.
        You will build dashboards, collaborate with analytics, and support stakeholders.
        Required skills: SQL, Excel, data analysis. Salary: CAD 80,000 to CAD 95,000.
        Interview process includes recruiter screen and final interview.
        """,
        country="India",
    )

    assert result.classification.label == "COUNTRY_RESTRICTED_REMOTE"
    restrictions = result.classification.evidence.remote_restrictions
    assert "Canada" in restrictions.allowed_countries
    assert restrictions.work_authorization


def test_classifies_hybrid_or_location_bound() -> None:
    result = analyze_text(
        """
        Company: OfficeWorks
        Job title: Product Manager
        Remote but office required three days per week. Must commute to Toronto.
        Responsibilities include roadmap planning and stakeholder collaboration.
        Required skills: communication, analytics. Salary: $100,000 to $120,000.
        """
    )

    assert result.classification.label == "HYBRID_OR_LOCATION_BOUND"
    assert result.classification.evidence.remote_restrictions.onsite_or_hybrid_requirement


def test_flexible_remote_options_are_not_hybrid_bound() -> None:
    result = analyze_text(
        """
        Company: Envisio
        Job title: Innovation Engineer
        We are seeking an Innovation Engineer who explores emerging technologies.
        Benefits include flexible work options (office, hybrid or remote).
        """
    )

    assert result.extracted.remote_type == "Flexible remote option"
    assert result.classification.label != "HYBRID_OR_LOCATION_BOUND"
    assert result.classification.evidence.remote_restrictions.onsite_or_hybrid_requirement is None


def test_hybrid_role_based_in_location_stays_location_bound() -> None:
    result = analyze_text(
        """
        Company: OfficeWorks
        Job title: Product Manager
        This is a hybrid role based in Toronto.
        Responsibilities include roadmap planning and stakeholder collaboration.
        Required skills: communication, analytics. Salary: $100,000 to $120,000.
        """
    )

    assert result.classification.label == "HYBRID_OR_LOCATION_BOUND"
    assert result.classification.evidence.remote_restrictions.onsite_or_hybrid_requirement


def test_classifies_low_quality_unverified() -> None:
    result = analyze_text(
        """
        Job title: Customer Success Manager
        Remote job. Help customers with simple tasks. Flexible hours.
        """
    )

    assert result.classification.label == "LOW_QUALITY_UNVERIFIED"
    assert result.classification.evidence.top_red_flags


def test_classifies_likely_scam_and_fallback_layers() -> None:
    result = analyze_text(
        """
        Job title: Remote Assistant
        Urgent hiring, no interview. Earn $500/day. Send money for equipment fee.
        Contact hiringteam@gmail.com or Telegram for gift cards and processing fee.
        """
    )

    assert result.classification.label == "LIKELY_SCAM"
    assert result.classification.layer_scores["transformer"].status == "unavailable"
    assert result.classification.layer_scores["structured_ml"].status == "unavailable"
    assert result.classification.status == "fallback"
    assert result.classification.fallback_reason
