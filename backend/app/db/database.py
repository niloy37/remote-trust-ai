from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompanyVerification,
    FeedbackRequest,
    FeedbackResponse,
    GraphVerification,
    JobClassification,
    JobRecord,
    Scores,
    ExtractedJob,
    TitleValidation,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def get_connection() -> sqlite3.Connection:
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                job_url TEXT,
                job_description TEXT NOT NULL,
                applicant_country TEXT NOT NULL,
                desired_role TEXT,
                final_score INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                legitimacy_score INTEGER NOT NULL,
                remote_authenticity_score INTEGER NOT NULL,
                global_eligibility_score INTEGER NOT NULL,
                job_quality_score INTEGER NOT NULL,
                title_validation_json TEXT,
                company_verification_json TEXT,
                graph_verification_json TEXT,
                classification_json TEXT,
                extracted_json TEXT NOT NULL,
                red_flags_json TEXT NOT NULL,
                positive_signals_json TEXT NOT NULL,
                extraction_warnings_json TEXT,
                explanation TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        if "title_validation_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN title_validation_json TEXT")
        if "company_verification_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN company_verification_json TEXT")
        if "graph_verification_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN graph_verification_json TEXT")
        if "classification_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN classification_json TEXT")
        if "extraction_warnings_json" not in columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN extraction_warnings_json TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                observations INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                evidence TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_kind_key ON graph_nodes(kind, normalized_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_job ON graph_edges(job_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source_type ON graph_edges(source_id, type)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                user_feedback TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )
        connection.commit()


def reset_db() -> None:
    db_path = Path(settings.sqlite_path)
    if db_path.exists():
        db_path.unlink()
    init_db()


def insert_job(request: AnalyzeRequest, response: AnalyzeResponse) -> JobRecord:
    created_at = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, job_url, job_description, applicant_country, desired_role,
                final_score, verdict, legitimacy_score, remote_authenticity_score,
                global_eligibility_score, job_quality_score, title_validation_json, company_verification_json,
                graph_verification_json, classification_json, extracted_json,
                red_flags_json, positive_signals_json, extraction_warnings_json, explanation,
                recommended_action, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response.job_id,
                request.job_url,
                request.job_description,
                request.applicant_country,
                request.desired_role,
                response.final_score,
                response.verdict,
                response.scores.legitimacy,
                response.scores.remote_authenticity,
                response.scores.global_eligibility,
                response.scores.job_quality,
                response.title_validation.model_dump_json(),
                response.company_verification.model_dump_json(),
                response.graph_verification.model_dump_json(),
                response.classification.model_dump_json(),
                response.extracted.model_dump_json(),
                json.dumps(response.red_flags),
                json.dumps(response.positive_signals),
                json.dumps(response.extraction_warnings),
                response.explanation,
                response.recommended_action,
                created_at,
            ),
        )
        connection.commit()
    return JobRecord(**response.model_dump(), **request.model_dump(), created_at=created_at)


def row_to_job(row: sqlite3.Row) -> JobRecord:
    extracted_json = json.loads(row["extracted_json"])
    title_validation_json = row["title_validation_json"] if "title_validation_json" in row.keys() else None
    company_verification_json = row["company_verification_json"] if "company_verification_json" in row.keys() else None
    graph_verification_json = row["graph_verification_json"] if "graph_verification_json" in row.keys() else None
    classification_json = row["classification_json"] if "classification_json" in row.keys() else None
    extraction_warnings_json = row["extraction_warnings_json"] if "extraction_warnings_json" in row.keys() else None
    title_validation = (
        TitleValidation(**json.loads(title_validation_json))
        if title_validation_json
        else TitleValidation(
            original_title=extracted_json.get("job_title"),
            normalized_title=None,
            verdict="Unusual",
            score=45,
            warnings=["No stored title validation is available for this older analysis"],
        )
    )
    company_verification = (
        CompanyVerification(**json.loads(company_verification_json))
        if company_verification_json
        else CompanyVerification(
            company=extracted_json.get("company"),
            status="Limited evidence",
            score=45,
            searched_at=row["created_at"],
            warnings=["No stored web verification is available for this older analysis"],
        )
    )
    graph_verification = (
        GraphVerification(**json.loads(graph_verification_json))
        if graph_verification_json
        else GraphVerification(
            status="Limited graph evidence",
            score=45,
            entity_confidence=30,
            warnings=["No stored relationship evidence is available for this older analysis"],
        )
    )
    classification = (
        JobClassification(**json.loads(classification_json))
        if classification_json
        else JobClassification(
            label="LEGIT_REMOTE" if row["final_score"] >= 80 else "LOW_QUALITY_UNVERIFIED" if row["final_score"] >= 60 else "LIKELY_SCAM",
            confidence=0.5,
            recommendation=row["recommended_action"],
            status="fallback",
            fallback_reason="No stored advanced classification is available for this older analysis",
            layer_scores={
                "rules": {
                    "status": "available",
                    "score": row["final_score"] / 100,
                    "probabilities": {},
                    "evidence": json.loads(row["positive_signals_json"])[:2] + json.loads(row["red_flags_json"])[:2],
                }
            },
            evidence={
                "top_red_flags": json.loads(row["red_flags_json"])[:5] or ["No stored red flags"],
                "positive_signals": json.loads(row["positive_signals_json"])[:5] or ["No stored positive signals"],
                "remote_restrictions": {
                    "allowed_countries": extracted_json.get("allowed_countries", []),
                    "excluded_countries": [],
                    "timezone_requirements": extracted_json.get("timezone_requirements"),
                    "work_authorization": extracted_json.get("work_authorization"),
                    "onsite_or_hybrid_requirement": None,
                    "ambiguous_location_language": [],
                    "source_snippets": [],
                },
                "graph_summary": {"status": graph_verification.status, "score": graph_verification.score},
                "confidence_factors": ["Classification was synthesized from an older saved score"],
                "explanation": "Older saved analysis was converted to the advanced classification shape.",
            },
        )
    )
    return JobRecord(
        job_id=row["id"],
        job_url=row["job_url"],
        job_description=row["job_description"],
        applicant_country=row["applicant_country"],
        desired_role=row["desired_role"],
        final_score=row["final_score"],
        verdict=row["verdict"],
        scores=Scores(
            legitimacy=row["legitimacy_score"],
            remote_authenticity=row["remote_authenticity_score"],
            global_eligibility=row["global_eligibility_score"],
            job_quality=row["job_quality_score"],
        ),
        extracted=ExtractedJob(**extracted_json),
        title_validation=title_validation,
        company_verification=company_verification,
        graph_verification=graph_verification,
        classification=classification,
        red_flags=json.loads(row["red_flags_json"]),
        positive_signals=json.loads(row["positive_signals_json"]),
        extraction_warnings=json.loads(extraction_warnings_json) if extraction_warnings_json else [],
        explanation=row["explanation"],
        recommended_action=row["recommended_action"],
        created_at=row["created_at"],
    )


def list_jobs() -> list[JobRecord]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [row_to_job(row) for row in rows]


def get_job(job_id: str) -> JobRecord | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_job(row) if row else None


def insert_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    feedback_id = str(uuid.uuid4())
    created_at = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO feedback (id, job_id, user_feedback, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (feedback_id, feedback.job_id, feedback.user_feedback, feedback.notes, created_at),
        )
        connection.commit()
    return FeedbackResponse(id=feedback_id, created_at=created_at, **feedback.model_dump())


def database_status() -> str:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")
        return "ok"
    except sqlite3.Error as exc:
        return f"error: {exc}"
