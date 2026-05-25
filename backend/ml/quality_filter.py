from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # scikit-learn is installed in the backend image; keep local fallbacks graceful.
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
except Exception:  # pragma: no cover
    joblib = None
    TfidfVectorizer = None
    LogisticRegression = None
    Pipeline = None

from .feature_extractor import is_search_or_collection_url, text_looks_like_search_collection
from .scorer import analyze_job_text


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "sample_labeled_jobs.csv"
ARTIFACT_PATH = ROOT / "artifacts" / "baseline_model.joblib"

REJECTED_LABELS = {"fake", "suspicious"}
QUALITY_WEIGHTS = {
    "high_quality_remote": 1.0,
    "legitimate": 0.88,
    "restricted_remote": 0.74,
    "suspicious": 0.18,
    "fake": 0.0,
}
SEVERE_SCAM_TERMS = {
    "send money",
    "gift card",
    "gift cards",
    "wire transfer",
    "equipment fee",
    "processing fee",
    "crypto",
}


@dataclass
class MLQualityPrediction:
    label: str
    confidence: float
    quality_score: float
    probabilities: dict[str, float] = field(default_factory=dict)
    source: str = "unavailable"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobQualityDecision:
    accepted: bool
    label: str
    score: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ml_prediction: MLQualityPrediction | None = None
    word_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ml_prediction"] = self.ml_prediction.as_dict() if self.ml_prediction else None
        return data


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9+#.'-]+", text or ""))


def _load_dataset(path: Path = DATASET_PATH) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            if text and label:
                texts.append(text)
                labels.append(label)
    return texts, labels


@lru_cache(maxsize=1)
def _quality_model() -> tuple[Any | None, str]:
    if joblib is not None and ARTIFACT_PATH.exists():
        try:
            return joblib.load(ARTIFACT_PATH), "artifact"
        except Exception:
            pass

    if not all([TfidfVectorizer, LogisticRegression, Pipeline]) or not DATASET_PATH.exists():
        return None, "unavailable"

    try:
        texts, labels = _load_dataset()
        if len(texts) < 4 or len(set(labels)) < 2:
            return None, "unavailable"
        model = Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=4000)),
                ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
            ]
        )
        model.fit(texts, labels)
        return model, "trained_from_sample"
    except Exception:
        return None, "unavailable"


def predict_quality(text: str) -> MLQualityPrediction | None:
    model, source = _quality_model()
    if model is None:
        return None

    try:
        if hasattr(model, "predict_proba"):
            classes = list(model.classes_)
            values = model.predict_proba([text])[0]
            probabilities = {label: round(float(value), 4) for label, value in zip(classes, values, strict=True)}
            label = max(probabilities, key=probabilities.get)
            confidence = probabilities[label]
        else:
            label = str(model.predict([text])[0])
            confidence = 0.55
            probabilities = {label: confidence}
    except Exception:
        return None

    quality_score = sum(QUALITY_WEIGHTS.get(label, 0.3) * probability for label, probability in probabilities.items())
    return MLQualityPrediction(
        label=label,
        confidence=round(float(confidence), 4),
        quality_score=round(float(quality_score), 4),
        probabilities=probabilities,
        source=source,
    )


def quality_label(score: float) -> str:
    if score >= 0.72:
        return "high_quality"
    if score >= 0.52:
        return "reviewable_quality"
    return "low_quality"


def assess_job_quality(
    *,
    job_description: str,
    job_url: str | None,
    applicant_country: str,
    desired_role: str | None = None,
) -> tuple[JobQualityDecision, Any]:
    analysis = analyze_job_text(
        job_description=job_description,
        applicant_country=applicant_country,
        job_url=job_url,
        desired_role=desired_role,
    )
    ml_prediction = predict_quality(job_description)
    words = word_count(job_description)
    reasons: list[str] = []
    warnings = list(dict.fromkeys(analysis.extraction_warnings))
    extracted = analysis.extracted
    lower = job_description.lower()

    if len(job_description.strip()) < 180 or words < 45:
        reasons.append("Job text is too short for reliable ingestion.")
    if is_search_or_collection_url(job_url) or text_looks_like_search_collection(job_description):
        reasons.append("Source looks like a search/listing page rather than one individual posting.")
    if not extracted.company and not extracted.job_title:
        reasons.append("Neither company nor job title could be reliably extracted.")
    if analysis.title_validation.verdict == "Suspicious":
        reasons.append("Job title looks fabricated, clickbait-like, or inconsistent with the description.")
    elif analysis.title_validation.verdict == "Unusual" and analysis.title_validation.score < 35:
        reasons.append("Job title is unusually weak for an automated feed.")
    if analysis.scores.legitimacy < 40:
        reasons.append("Legitimacy score is below the ingestion safety threshold.")
    if analysis.scores.job_quality < 35:
        reasons.append("Job quality score is below the ingestion completeness threshold.")
    if analysis.final_score < 48:
        reasons.append("Overall trust score is too low for the curated ingestion layer.")
    if any(term in lower for term in SEVERE_SCAM_TERMS):
        reasons.append("Posting includes severe scam/payment language.")
    if extracted.suspicious_contact_methods and analysis.scores.legitimacy < 62:
        reasons.append("Suspicious personal contact method appears with weak legitimacy evidence.")
    if ml_prediction and ml_prediction.label in REJECTED_LABELS and ml_prediction.confidence >= 0.40:
        reasons.append(f"ML quality model classified the posting as {ml_prediction.label}.")
    if ml_prediction and ml_prediction.quality_score < 0.34 and analysis.final_score < 62:
        reasons.append("ML quality score is below the ingestion threshold.")

    base_score = analysis.final_score / 100
    ml_score = ml_prediction.quality_score if ml_prediction else base_score
    combined_score = round((base_score * 0.55) + (ml_score * 0.45), 4)
    if not reasons and combined_score < 0.52:
        reasons.append("Combined ML and rule quality score is below the publishable threshold.")

    decision = JobQualityDecision(
        accepted=not reasons,
        label=quality_label(combined_score),
        score=combined_score,
        reasons=list(dict.fromkeys(reasons)),
        warnings=warnings,
        ml_prediction=ml_prediction,
        word_count=words,
    )
    return decision, analysis
