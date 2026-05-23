from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .advanced_features import RemoteRestrictionEvidence, StructuredFeatureRecord, build_structured_features
from .dataset_schema import CLASSIFICATION_LABELS
from .schemas import ExtractedJob, ScoreBreakdown


Label = str
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


@dataclass
class LayerScore:
    status: str
    probabilities: dict[Label, float] = field(default_factory=dict)
    score: float | None = None
    evidence: list[str] = field(default_factory=list)
    reason: str | None = None

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
    label: Label
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


def _blank_probabilities() -> dict[Label, float]:
    return {label: 0.0 for label in CLASSIFICATION_LABELS}


def _probabilities_for(label: Label, confidence: float) -> dict[Label, float]:
    remaining = max(0.0, 1.0 - confidence)
    other = remaining / (len(CLASSIFICATION_LABELS) - 1)
    probabilities = {item: round(other, 3) for item in CLASSIFICATION_LABELS}
    probabilities[label] = round(confidence, 3)
    return probabilities


def _label_from_rules(
    scores: ScoreBreakdown,
    extracted: ExtractedJob,
    red_flags: list[str],
    features: StructuredFeatureRecord,
) -> tuple[Label, float, list[str]]:
    lower_flags = " ".join(red_flags).lower()
    restrictions = features.remote_restrictions
    confidence_factors: list[str] = []
    final_score = features.rule_score

    has_scam_language = any(term in lower_flags for term in ["scam", "payment", "gift card", "wire transfer", "no-interview", "suspicious personal"])
    if (
        (scores.legitimacy < 45 and has_scam_language)
        or features.has_payment_request
        or extracted.suspicious_contact_methods
        or has_scam_language
    ):
        confidence_factors.append("Legitimacy and scam-risk signals dominate the prediction")
        return "LIKELY_SCAM", 0.86 if scores.legitimacy < 35 or features.has_payment_request else 0.74, confidence_factors

    if restrictions.onsite_or_hybrid_requirement or (extracted.remote_type or "").lower() in {"hybrid", "onsite"}:
        confidence_factors.append("Remote claim conflicts with onsite or hybrid requirements")
        return "HYBRID_OR_LOCATION_BOUND", 0.78, confidence_factors

    has_country_allowlist = bool(restrictions.allowed_countries) and "Worldwide" not in restrictions.allowed_countries
    if has_country_allowlist or restrictions.work_authorization or restrictions.timezone_requirements or restrictions.ambiguous_location_language:
        confidence_factors.append("Remote work includes location, authorization, or timezone restrictions")
        return "COUNTRY_RESTRICTED_REMOTE", 0.76, confidence_factors

    if final_score >= 78 and scores.remote_authenticity >= 70 and scores.legitimacy >= 70:
        confidence_factors.append("High rule score with clear legitimacy and remote-authenticity evidence")
        return "LEGIT_REMOTE", 0.80, confidence_factors

    confidence_factors.append("Evidence is not strong enough for verified remote or likely scam labels")
    return "LOW_QUALITY_UNVERIFIED", 0.66 if final_score < 60 else 0.58, confidence_factors


def _recommended_action(label: Label, rule_score: int) -> str:
    if label == "LEGIT_REMOTE" and rule_score >= 70:
        return "Apply"
    if label == "LIKELY_SCAM":
        return "Avoid"
    return "Review carefully"


def _graph_summary(graph_verification: Any | None) -> dict[str, Any]:
    if graph_verification is None:
        return {
            "status": "unavailable",
            "score": 0,
            "signals": [],
            "warnings": ["Graph verification was not available for this analysis"],
            "evidence_paths": [],
        }
    return {
        "status": getattr(graph_verification, "status", "unavailable"),
        "score": getattr(graph_verification, "score", 0),
        "signals": list(getattr(graph_verification, "signals", []) or []),
        "warnings": list(getattr(graph_verification, "warnings", []) or []),
        "evidence_paths": list(getattr(graph_verification, "evidence_paths", []) or []),
    }


def classify_job(
    job_description: str,
    extracted: ExtractedJob,
    scores: ScoreBreakdown,
    red_flags: list[str],
    positive_signals: list[str],
    company_verification_score: int = 0,
    graph_verification: Any | None = None,
) -> JobClassification:
    graph_score = int(getattr(graph_verification, "score", 0) or 0)
    features = build_structured_features(job_description, extracted, scores, company_verification_score, graph_score)
    label, confidence, confidence_factors = _label_from_rules(scores, extracted, red_flags, features)
    probabilities = _probabilities_for(label, confidence)
    graph_summary = _graph_summary(graph_verification)

    fallback_reason = "Advanced trained artifacts are optional for the MVP; deterministic local rules produced this classification"
    layers = {
        "transformer": LayerScore(
            status="unavailable",
            probabilities=_blank_probabilities(),
            reason="No local transformer artifact is required or loaded for the MVP baseline",
        ),
        "structured_ml": LayerScore(
            status="unavailable",
            probabilities=_blank_probabilities(),
            evidence=[
                f"Extracted {len(features.skills)} skills",
                f"Apply domain: {features.apply_domain or 'not detected'}",
            ],
            reason="No local structured ML artifact is required or loaded for the MVP baseline",
        ),
        "rules": LayerScore(
            status="available",
            probabilities=probabilities,
            score=round(features.rule_score / 100, 3),
            evidence=[*positive_signals[:3], *red_flags[:3]],
        ),
        "graph": LayerScore(
            status="available" if graph_score else "degraded",
            probabilities=probabilities,
            score=round(graph_score / 100, 3) if graph_score else None,
            evidence=[*graph_summary["signals"][:2], *graph_summary["warnings"][:2]],
            reason=None if graph_score else "Graph score was unavailable or empty",
        ),
        "meta": LayerScore(
            status="degraded",
            probabilities=probabilities,
            score=confidence,
            evidence=confidence_factors,
            reason="Meta-classifier is using deterministic fallback until trained artifacts are available",
        ),
    }

    explanation = (
        f"{label.replace('_', ' ').title()} with {round(confidence * 100)}% confidence. "
        f"{confidence_factors[0] if confidence_factors else fallback_reason}."
    )
    evidence = ClassificationEvidence(
        top_red_flags=red_flags[:5] or ["No major red flags detected"],
        positive_signals=positive_signals[:5] or ["Limited positive signals detected"],
        remote_restrictions=features.remote_restrictions,
        graph_summary=graph_summary,
        confidence_factors=confidence_factors,
        explanation=explanation,
    )
    return JobClassification(
        label=label,
        confidence=round(confidence, 3),
        recommendation=_recommended_action(label, features.rule_score),
        layer_scores=layers,
        evidence=evidence,
        status="fallback",
        fallback_reason=fallback_reason,
    )
