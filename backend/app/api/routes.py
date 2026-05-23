from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.db.database import database_status, get_job, insert_feedback, insert_job, list_jobs
from app.models import AnalyzeRequest, AnalyzeResponse, FeedbackRequest, FeedbackResponse, HealthResponse, JobRecord
from app.services.analyzer import analyze


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        database=database_status(),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_job(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        response = analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    insert_job(request, response)
    return response


@router.get("/jobs", response_model=list[JobRecord])
def jobs() -> list[JobRecord]:
    return list_jobs()


@router.get("/jobs/{job_id}", response_model=JobRecord)
def job(job_id: str) -> JobRecord:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return record


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(payload: FeedbackRequest) -> FeedbackResponse:
    if not get_job(payload.job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return insert_feedback(payload)

