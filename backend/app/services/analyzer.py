from __future__ import annotations

import sys
import uuid
from pathlib import Path

from app.models import AnalyzeRequest, AnalyzeResponse, CompanyVerification, ExtractedJob, GraphVerification, Scores, TitleValidation
from app.services.graph_verifier import verify_relationship_graph
from app.services.job_fetcher import JobFetchError, fetch_job_description
from app.services.web_verifier import verify_company_web


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.advanced_classifier import classify_job  # noqa: E402
from ml.feature_extractor import clean_job_text  # noqa: E402
from ml.scorer import analyze_job_text  # noqa: E402


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def add_unique(items: list[str], item: str) -> None:
    if item and item not in items:
        items.append(item)


def trust_score(scores: Scores) -> int:
    return round(
        scores.legitimacy * 0.40
        + scores.remote_authenticity * 0.25
        + scores.global_eligibility * 0.20
        + scores.job_quality * 0.15
    )


def verdict_for(final_score: int) -> str:

    if final_score >= 80:
        return "Verified"

    if final_score >= 60:
        return "Caution"

    if final_score >= 40:
        return "Risky"

    return "Risky"



def recommended_action_for(
    final_score: int,
    classification_label: str | None = None,
    red_flags: list[str] | None = None,
    company_verification: CompanyVerification | None = None,
    graph_verification: GraphVerification | None = None,
) -> str:
    red_text = " ".join(red_flags or []).lower()
    severe_risk = (
        classification_label == "LIKELY_SCAM"
        or final_score < 45
        or "payment request" in red_text
        or "gift card" in red_text
        or "wire transfer" in red_text
        or "suspicious personal recruiter contact" in red_text
        or company_verification is not None
        and company_verification.status == "Risk signals"
        or graph_verification is not None
        and graph_verification.status == "Risk signals"
        and final_score < 55
    )
    if severe_risk:
        return "Avoid"
    if final_score >= 80 and classification_label == "LEGIT_REMOTE":
        return "Apply"
    return "Review carefully"

def apply_graph_adjustments(scores: Scores, graph_verification: GraphVerification, had_existing_red_flags: bool) -> Scores:
    if graph_verification.status == "Strong graph evidence":
        return Scores(
            legitimacy=clamp(scores.legitimacy + 4),
            remote_authenticity=scores.remote_authenticity,
            global_eligibility=scores.global_eligibility,
            job_quality=clamp(scores.job_quality + 1),
        )
    if graph_verification.status == "Some graph evidence":
        return Scores(
            legitimacy=clamp(scores.legitimacy + 2),
            remote_authenticity=scores.remote_authenticity,
            global_eligibility=scores.global_eligibility,
            job_quality=scores.job_quality,
        )
    if graph_verification.status == "Risk signals":
        legitimacy_penalty = 8 if had_existing_red_flags else 4
        quality_penalty = 5 if had_existing_red_flags else 2
        return Scores(
            legitimacy=clamp(scores.legitimacy - legitimacy_penalty),
            remote_authenticity=scores.remote_authenticity,
            global_eligibility=scores.global_eligibility,
            job_quality=clamp(scores.job_quality - quality_penalty),
        )
    return scores


def merge_graph_evidence(
    graph_verification: GraphVerification,
    company_verification: CompanyVerification,
    red_flags: list[str],
    positive_signals: list[str],
) -> None:
    if graph_verification.status in {"Strong graph evidence", "Some graph evidence"}:
        for signal in graph_verification.signals[:2]:
            add_unique(positive_signals, signal)
            add_unique(company_verification.signals, signal)
    elif graph_verification.status == "Risk signals":
        for warning in graph_verification.warnings[:2]:
            add_unique(red_flags, warning)
            add_unique(company_verification.warnings, warning)
    else:
        for warning in graph_verification.warnings[:1]:
            add_unique(company_verification.warnings, warning)


def build_explanation(
    scores: Scores,
    verdict: str,
    red_flags: list[str],
    positive_signals: list[str],
    graph_verification: GraphVerification,
) -> str:
    score_map = scores.model_dump()
    strongest = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    best_name, best_score = strongest[0]
    weakest_name, weakest_score = strongest[-1]
    red_summary = red_flags[0] if red_flags else "No severe scam indicators were detected"
    positive_summary = positive_signals[0] if positive_signals else "The posting has limited positive verification signals"
    relationship_summary = {
        "Strong graph evidence": "Company identity, domains, and application path show strong supporting relationship evidence.",
        "Some graph evidence": "Company identity and application details have some supporting relationship evidence.",
        "Risk signals": "Relationship checks found identity, contact, or domain inconsistencies that should be reviewed carefully.",
        "Limited graph evidence": "Relationship evidence is limited, so the company identity should be checked before applying.",
    }[graph_verification.status]
    return (
        f"RemoteTrust AI marked this job as {verdict} because its strongest pillar is "
        f"{best_name.replace('_', ' ')} at {best_score}/100, while {weakest_name.replace('_', ' ')} "
        f"is the main constraint at {weakest_score}/100. {positive_summary}. {red_summary}. "
        f"{relationship_summary}"
    )


def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    description = request.job_description.strip()
    fetch_source: str | None = None
    fetch_warning: str | None = None
    if not description and request.job_url:
        try:
            fetched = fetch_job_description(request.job_url)
        except JobFetchError as exc:
            raise ValueError(str(exc)) from exc
        description = fetched.text
        fetch_source = fetched.source
        fetch_warning = fetched.warning
        request.job_description = description

    analysis_description = clean_job_text(description)
    result = analyze_job_text(
        job_description=analysis_description,
        applicant_country=request.applicant_country,
        job_url=request.job_url,
        desired_role=request.desired_role,
    )
    if fetch_source:
        result.positive_signals.insert(0, f"Job description fetched from URL using {fetch_source}")
    if fetch_warning:
        result.red_flags.append(fetch_warning)

    company_verification_raw = verify_company_web(
        result.extracted.company,
        result.extracted.apply_url,
        result.extracted.company_confidence,
        result.extracted.company_evidence,
    )
    company_verification = CompanyVerification(**company_verification_raw.model_dict())
    scores = Scores(**result.scores.as_dict())
    if company_verification.status == "Strong evidence":
        scores.legitimacy = min(100, scores.legitimacy + 4)
        result.positive_signals.insert(0, "Live web verification found strong company evidence")
    elif company_verification.status == "Some evidence":
        scores.legitimacy = min(100, scores.legitimacy + 2)
        result.positive_signals.insert(0, "Live web verification found supporting company evidence")
    elif company_verification.status == "Risk signals":
        scores.legitimacy = max(0, scores.legitimacy - 8)
        result.red_flags.insert(0, "Live web verification found company risk signals")

    job_id = str(uuid.uuid4())
    pre_graph_final_score = trust_score(scores)
    had_existing_red_flags = bool(result.red_flags)
    graph_verification = verify_relationship_graph(
        job_id=job_id,
        request=request,
        extracted=result.extracted,
        company_verification=company_verification,
        red_flags=result.red_flags,
        job_description=analysis_description,
    )
    merge_graph_evidence(graph_verification, company_verification, result.red_flags, result.positive_signals)
    scores = apply_graph_adjustments(scores, graph_verification, had_existing_red_flags)
    final_score = trust_score(scores)
    if (
        graph_verification.status == "Risk signals"
        and not had_existing_red_flags
        and pre_graph_final_score >= 60
        and final_score < 60
    ):
        final_score = 60
    verdict = verdict_for(final_score)
    classification = classify_job(
        job_description=analysis_description,
        extracted=result.extracted,
        scores=result.scores,
        red_flags=result.red_flags,
        positive_signals=result.positive_signals,
        company_verification_score=company_verification.score,
        graph_verification=graph_verification,
    )
    recommended_action = recommended_action_for(
        final_score,
        classification.label,
        result.red_flags,
        company_verification,
        graph_verification,
    )

    return AnalyzeResponse(
        job_id=job_id,
        final_score=final_score,
        verdict=verdict,
        scores=scores,
        extracted=ExtractedJob(**result.extracted.public_dict()),
        title_validation=TitleValidation(**result.title_validation.as_dict()),
        company_verification=company_verification,
        graph_verification=graph_verification,
        classification=classification.as_dict(),
        red_flags=result.red_flags,
        positive_signals=result.positive_signals,
        extraction_warnings=result.extraction_warnings,
        explanation=f"{build_explanation(scores, verdict, result.red_flags, result.positive_signals, graph_verification)} {classification.evidence.explanation}",
        recommended_action=recommended_action,
    )
