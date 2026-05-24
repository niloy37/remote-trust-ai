from __future__ import annotations

import os
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
from app.services.job_fetcher import JobFetchError, fetch_job_description
from app.services.web_verifier import WebSource, classify_source, score_sources, verify_company_web, verify_company_web_cached
from ml.feature_extractor import company_candidate_rejection_reason, extract_features


ENVISIO_POSTING = """
We are seeking an Innovation Engineer who is passionate about exploring emerging technologies and translating them into practical solutions that deliver meaningful business value.
This role focuses on rapid experimentation, applied problem solving, and technological discovery.

Why Envisio?

Envisio's award-winning software aligns staff with departmental action plans and key performance measures, enabling customers to establish trust with their stakeholders.
We've got great software, happy customers, and a passionate team.

Benefits

Extended health, dental and vision care
20 days vacation
Flexible work options (office, hybrid or remote)
Stock options
"""


def test_envisio_posting_extracts_company_and_title_without_fragment() -> None:
    extracted = extract_features(ENVISIO_POSTING)

    assert extracted.company == "Envisio"
    assert extracted.company_confidence and extracted.company_confidence >= 0.70
    assert extracted.company_evidence == "section heading"
    assert extracted.job_title == "Innovation Engineer"
    assert extracted.company != "software, happy customers"
    assert extracted.remote_type == "Flexible remote option"


def test_analyze_envisio_does_not_search_for_bad_company_fragment() -> None:
    old_enabled = os.environ.get("WEB_VERIFICATION_ENABLED")
    os.environ["WEB_VERIFICATION_ENABLED"] = "false"
    verify_company_web_cached.cache_clear()
    try:
        response = analyze(AnalyzeRequest(job_description=ENVISIO_POSTING, applicant_country="Canada"))
    finally:
        verify_company_web_cached.cache_clear()
        if old_enabled is None:
            os.environ.pop("WEB_VERIFICATION_ENABLED", None)
        else:
            os.environ["WEB_VERIFICATION_ENABLED"] = old_enabled

    assert response.extracted.company == "Envisio"
    assert response.classification.label != "HYBRID_OR_LOCATION_BOUND"
    assert response.classification.evidence.remote_restrictions.onsite_or_hybrid_requirement is None
    assert all("software, happy customers" not in query for query in response.company_verification.search_queries)


def test_company_extraction_sources_and_bad_fragments() -> None:
    assert extract_features("Company: ExampleCloud\nJob title: Backend Engineer").company == "ExampleCloud"
    assert extract_features("Why Envisio?\nWe build public-sector planning software.").company == "Envisio"
    assert extract_features("Innovation Engineer at Envisio").company == "Envisio"

    for fragment in ["software, happy customers", "building deep relationships", "our customers"]:
        assert company_candidate_rejection_reason(fragment)


def test_json_ld_jobposting_company_beats_ats_slug() -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Backend Engineer",
        "hiringOrganization": {"@type": "Organization", "name": "Acme Labs"},
        "description": "Build APIs, collaborate with teams, and operate production services."
      }
      </script>
    </body></html>
    """
    extracted = extract_features(html, "https://jobs.lever.co/not-acme/123")

    assert extracted.company == "Acme Labs"
    assert extracted.job_title == "Backend Engineer"
    assert extracted.company_confidence and extracted.company_confidence >= 0.95


def test_low_confidence_company_skips_live_web_verification() -> None:
    verification = verify_company_web("Maybe Corp", None, company_confidence=0.42, company_evidence="bounded text heuristic")

    assert verification.status == "Limited evidence"
    assert verification.search_queries == []
    assert "live company verification was skipped" in verification.warnings[0]


def test_valid_company_runs_normal_verification_path_when_search_disabled() -> None:
    old_enabled = os.environ.get("WEB_VERIFICATION_ENABLED")
    os.environ["WEB_VERIFICATION_ENABLED"] = "false"
    verify_company_web_cached.cache_clear()
    try:
        verification = verify_company_web("Envisio", None, company_confidence=0.94, company_evidence="explicit company label")
    finally:
        verify_company_web_cached.cache_clear()
        if old_enabled is None:
            os.environ.pop("WEB_VERIFICATION_ENABLED", None)
        else:
            os.environ["WEB_VERIFICATION_ENABLED"] = old_enabled

    assert verification.search_queries
    assert verification.company == "Envisio"
    assert "disabled" in verification.warnings[0]


def test_generic_career_result_does_not_score_without_company_match() -> None:
    source = WebSource(
        title="Careers and jobs",
        url="https://jobs.example.com/search",
        snippet="Browse open roles at many companies.",
        source_type="general_web_result",
    )
    source.source_type = classify_source("Envisio", source.title, source.url, source.snippet)
    score, signals, warnings = score_sources("Envisio", [source], None)

    assert source.source_type == "general_web_result"
    assert score < 58
    assert not signals
    assert any("No official company" in warning for warning in warnings)


def test_search_collection_text_does_not_infer_random_company_or_title() -> None:
    text = """
    FlexJobs Search Results
    1,234 remote jobs found
    Save search
    Recommended jobs
    Remote Project Manager - AcmeCloud
    Remote Data Analyst - NorthRemote
    Remote Customer Success - BrightCo
    Sign in to view job details
    Page 1 of 32
    """
    extracted = extract_features(text, "https://www.flexjobs.com/search?search=remote")

    assert extracted.company is None
    assert extracted.job_title is None
    assert extracted.extraction_warnings
    assert any("search" in warning.lower() or "collection" in warning.lower() for warning in extracted.extraction_warnings)


def test_search_url_is_rejected_before_crawling() -> None:
    try:
        fetch_job_description("https://www.flexjobs.com/search?search=remote")
    except JobFetchError as exc:
        assert "search, collection, or listing page" in str(exc)
    else:  # pragma: no cover - this should never try network for search URLs.
        raise AssertionError("Search URL should be rejected before crawling")


def test_supported_portal_json_ld_pages_extract_core_fields() -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Remote Product Designer",
        "hiringOrganization": {"@type": "Organization", "name": "DesignCloud"},
        "jobLocationType": "TELECOMMUTE",
        "description": "Fully remote. You will design workflows, collaborate with product teams, and prototype interfaces. Required skills: design, research, communication."
      }
      </script>
    </body></html>
    """
    urls = [
        "https://www.flexjobs.com/remote-jobs/designcloud-product-designer",
        "https://remoteok.com/remote-jobs/123456-remote-product-designer-designcloud",
        "https://weworkremotely.com/remote-jobs/designcloud-remote-product-designer",
        "https://remotive.com/remote-jobs/product/remote-product-designer-123",
        "https://wellfound.com/company/designcloud/jobs/123456-remote-product-designer",
    ]

    for url in urls:
        extracted = extract_features(html, url)
        assert extracted.company == "DesignCloud"
        assert extracted.job_title == "Remote Product Designer"
        assert extracted.remote_type == "Fully remote"
