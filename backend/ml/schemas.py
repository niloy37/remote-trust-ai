from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ExtractedJob:
    job_title: str | None = None
    company: str | None = None
    company_confidence: float | None = None
    company_evidence: str | None = None
    salary: str | None = None
    location: str | None = None
    remote_type: str | None = None
    allowed_countries: list[str] = field(default_factory=list)
    timezone_requirements: str | None = None
    work_authorization: str | None = None
    apply_url: str | None = None
    required_skills: list[str] = field(default_factory=list)
    seniority_level: str | None = None
    contact_methods: list[str] = field(default_factory=list)
    suspicious_contact_methods: list[str] = field(default_factory=list)
    scam_phrases: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            "job_title": data["job_title"],
            "company": data["company"],
            "company_confidence": data["company_confidence"],
            "company_evidence": data["company_evidence"],
            "salary": data["salary"],
            "location": data["location"],
            "remote_type": data["remote_type"],
            "allowed_countries": data["allowed_countries"],
            "timezone_requirements": data["timezone_requirements"],
            "work_authorization": data["work_authorization"],
            "apply_url": data["apply_url"],
        }

    def full_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreBreakdown:
    legitimacy: int
    remote_authenticity: int
    global_eligibility: int
    job_quality: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class TitleValidation:
    original_title: str | None
    normalized_title: str | None
    verdict: str
    score: int
    closest_known_titles: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    final_score: int
    verdict: str
    scores: ScoreBreakdown
    extracted: ExtractedJob
    title_validation: TitleValidation
    red_flags: list[str]
    positive_signals: list[str]
    extraction_warnings: list[str]
    explanation: str
    recommended_action: str


@dataclass
class LayerScore:
    status: str
    probabilities: dict[str, float] = field(default_factory=dict)
    score: float | None = None
    evidence: list[str] = field(default_factory=list)
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RemoteRestrictionEvidence:
    allowed_countries: list[str] = field(default_factory=list)
    excluded_countries: list[str] = field(default_factory=list)
    timezone_requirements: str | None = None
    work_authorization: str | None = None
    onsite_or_hybrid_requirement: str | None = None
    ambiguous_location_language: list[str] = field(default_factory=list)
    source_snippets: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationEvidence:
    top_red_flags: list[str]
    positive_signals: list[str]
    remote_restrictions: RemoteRestrictionEvidence
    graph_summary: dict[str, Any]
    confidence_factors: list[str]
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["remote_restrictions"] = self.remote_restrictions.as_dict()
        return data


@dataclass
class JobClassification:
    label: str
    confidence: float
    recommendation: str
    layer_scores: dict[str, LayerScore]
    evidence: ClassificationEvidence
    status: str = "fallback"
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "layer_scores": {key: value.as_dict() for key, value in self.layer_scores.items()},
            "evidence": self.evidence.as_dict(),
            "status": self.status,
            "fallback_reason": self.fallback_reason,
        }
