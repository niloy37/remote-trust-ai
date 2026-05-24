from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Verdict = Literal["Verified", "Caution", "Risky"]
FeedbackValue = Literal["applied", "not_apply", "reported_suspicious", "incorrect_score"]
ClassificationLabel = Literal[
    "LEGIT_REMOTE",
    "COUNTRY_RESTRICTED_REMOTE",
    "HYBRID_OR_LOCATION_BOUND",
    "LOW_QUALITY_UNVERIFIED",
    "LIKELY_SCAM",
]
LayerStatus = Literal["available", "skipped", "unavailable", "degraded"]


class AnalyzeRequest(BaseModel):
    job_url: str | None = None
    job_description: str = ""
    applicant_country: str = Field(..., min_length=2)
    desired_role: str | None = None

    @model_validator(mode="after")
    def require_url_or_description(self) -> "AnalyzeRequest":
        if not self.job_url and not self.job_description.strip():
            raise ValueError("Provide either a job URL or a job description.")
        return self


class Scores(BaseModel):
    legitimacy: int
    remote_authenticity: int
    global_eligibility: int
    job_quality: int


class ExtractedJob(BaseModel):
    job_title: str | None = None
    company: str | None = None
    company_confidence: float | None = None
    company_evidence: str | None = None
    salary: str | None = None
    location: str | None = None
    remote_type: str | None = None
    allowed_countries: list[str] = Field(default_factory=list)
    timezone_requirements: str | None = None
    work_authorization: str | None = None
    apply_url: str | None = None


class TitleValidation(BaseModel):
    original_title: str | None = None
    normalized_title: str | None = None
    verdict: Literal["Recognized", "Plausible", "Unusual", "Suspicious"]
    score: int
    closest_known_titles: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WebSource(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_type: str


class CompanyVerification(BaseModel):
    company: str | None = None
    status: Literal["Strong evidence", "Some evidence", "Limited evidence", "Risk signals"]
    score: int
    searched_at: str
    search_queries: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[WebSource] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    kind: str
    name: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    evidence: str | None = None


class GraphRelationshipEvidence(BaseModel):
    source_kind: str
    source_value: str
    target_kind: str
    target_value: str
    relationship_type: str
    status: Literal["supports", "conflicts", "unknown"]
    evidence: str | None = None


class GraphVerification(BaseModel):
    status: Literal["Strong graph evidence", "Some graph evidence", "Limited graph evidence", "Risk signals"]
    score: int
    entity_confidence: int
    relationship_status: str | None = None
    fallback_backend: Literal["neo4j", "sqlite", "none"] | None = None
    relationships: list[GraphRelationshipEvidence] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class LayerScore(BaseModel):
    status: LayerStatus
    probabilities: dict[ClassificationLabel, float] = Field(default_factory=dict)
    score: float | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None


class RemoteRestrictionEvidence(BaseModel):
    allowed_countries: list[str] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)
    timezone_requirements: str | None = None
    work_authorization: str | None = None
    onsite_or_hybrid_requirement: str | None = None
    ambiguous_location_language: list[str] = Field(default_factory=list)
    source_snippets: list[str] = Field(default_factory=list)


class ClassificationEvidence(BaseModel):
    top_red_flags: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    remote_restrictions: RemoteRestrictionEvidence
    graph_summary: dict = Field(default_factory=dict)
    confidence_factors: list[str] = Field(default_factory=list)
    explanation: str


class JobClassification(BaseModel):
    label: ClassificationLabel
    confidence: float = Field(ge=0, le=1)
    recommendation: str
    layer_scores: dict[str, LayerScore]
    evidence: ClassificationEvidence
    status: Literal["complete", "degraded", "fallback"]
    fallback_reason: str | None = None


class AnalyzeResponse(BaseModel):
    job_id: str
    final_score: int
    verdict: Verdict
    scores: Scores
    extracted: ExtractedJob
    title_validation: TitleValidation
    company_verification: CompanyVerification
    graph_verification: GraphVerification
    classification: JobClassification
    red_flags: list[str]
    positive_signals: list[str]
    extraction_warnings: list[str] = Field(default_factory=list)
    explanation: str
    recommended_action: Literal["Apply", "Review carefully", "Avoid"]


class JobRecord(AnalyzeResponse):
    job_url: str | None = None
    job_description: str
    applicant_country: str
    desired_role: str | None = None
    created_at: str


class FeedbackRequest(BaseModel):
    job_id: str
    user_feedback: FeedbackValue
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    job_id: str
    user_feedback: FeedbackValue
    notes: str | None = None
    created_at: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
