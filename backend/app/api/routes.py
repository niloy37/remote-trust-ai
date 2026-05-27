from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.db.database import database_status, get_job, insert_feedback, insert_job, list_jobs
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IngestionQueueRequest,
    IngestionQueueResponse,
    IngestionRunSummary,
    IngestionStatusResponse,
    JobRecord,
    OpportunityFeedResponse,
)
from app.services.analyzer import analyze
from app.services.ingestion import enqueue_url, ingestion_status, opportunity_feed, run_ingestion


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

@router.get("/opportunities", response_model=OpportunityFeedResponse)
def opportunities() -> OpportunityFeedResponse:
    feed = opportunity_feed()

    if not feed.jobs:
        demo_jobs = [
            {
                "job_id": "demo-001",
                "title": "Senior Software Engineer",
                "company": "Northstar Labs",
                "location": "Remote Worldwide",
                "score": 92,
                "classification": "LEGIT_REMOTE",
                "apply_url": "https://jobs.greenhouse.io/northstarlabs/jobs/remote-senior-software-engineer",
                "summary": "Remote-first engineering role with verified hiring signals, transparent salary, and async collaboration."
            },
            {
                "job_id": "demo-002",
                "title": "Data Analyst",
                "company": "Atlas Metrics",
                "location": "Remote Worldwide",
                "score": 88,
                "classification": "LEGIT_REMOTE",
                "apply_url": "https://jobs.greenhouse.io/atlasmetrics/jobs/data-analyst-remote",
                "summary": "High-quality remote data analyst role with SQL, analytics, and async team collaboration."
            },
            {
                "job_id": "demo-003",
                "title": "Backend Engineer",
                "company": "RouteForge",
                "location": "Remote Worldwide",
                "score": 90,
                "classification": "LEGIT_REMOTE",
                "apply_url": "https://jobs.lever.co/routeforge/backend-engineer-go",
                "summary": "Distributed systems backend role focused on Go APIs, observability, and cloud infrastructure."
            },
            {
                "job_id": "demo-004",
                "title": "Product Designer",
                "company": "BrightCanvas",
                "location": "Europe Remote",
                "score": 85,
                "classification": "COUNTRY_RESTRICTED_REMOTE",
                "apply_url": "https://jobs.lever.co/brightcanvas/product-designer-remote",
                "summary": "Remote UX/product design role with strong accessibility and collaboration practices."
            },
            {
                "job_id": "demo-005",
                "title": "Security Engineer",
                "company": "SafeCircuit",
                "location": "United States & Canada",
                "score": 93,
                "classification": "LEGIT_REMOTE",
                "apply_url": "https://jobs.ashbyhq.com/safecircuit/security-engineer",
                "summary": "Application security engineering role supporting secure SDLC workflows and cloud security."
            }
        ]

        feed.jobs = demo_jobs

        feed.summary.jobs_collected = len(demo_jobs)
        feed.summary.verified_opportunities = len(demo_jobs)
        feed.summary.ingestion_status = "demo_seeded"

    return feed

""" @router.get("/opportunities", response_model=OpportunityFeedResponse)
def opportunities() -> OpportunityFeedResponse:
    return opportunity_feed()
 """

@router.post("/ingestion/run", response_model=IngestionRunSummary)
def ingestion_run() -> IngestionRunSummary:
    return run_ingestion()


@router.get("/ingestion/status", response_model=IngestionStatusResponse)
def ingestion_status_endpoint() -> IngestionStatusResponse:
    return ingestion_status()


@router.post("/ingestion/queue", response_model=IngestionQueueResponse)
def ingestion_queue(payload: IngestionQueueRequest) -> IngestionQueueResponse:
    try:
        return enqueue_url(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
