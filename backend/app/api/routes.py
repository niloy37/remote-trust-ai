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
                "applicant_country": "India",
                "desired_role": "Software Engineer",
                "final_score": 92,
                "verdict": "Verified",
                "recommended_action": "Apply",

                "analysis_summary": "Verified remote engineering opportunity with strong trust signals.",
                "risk_level": "Low",

                "flags": [],
                "warnings": [],

                "trust_signals": [
                    "Verified ATS link",
                    "Transparent compensation"
                ],

                "reasons": [
                    "Remote-first organization"
                ],

                "evidence": [
                    "Official careers portal"
                ],

                "classification": {
                    "label": "LEGIT_REMOTE"
                },

                "scores": {
                    "remote_authenticity": 95,
                    "legitimacy": 94,
                    "job_quality": 91,
                    "global_eligibility": 89
                },

                "layer_scores": {},

                "country_fit": {
                    "eligible": True
                },

                "company_verification": {
                    "status": "Verified"
                },

                "extracted": {
                    "job_title": "Senior Software Engineer",
                    "company": "Northstar Labs",
                    "remote_type": "Fully Remote",
                    "apply_url": "https://jobs.greenhouse.io/northstarlabs/jobs/remote-senior-software-engineer"
                }
            },

            {
                "job_id": "demo-002",
                "applicant_country": "Canada",
                "desired_role": "Data Analyst",
                "final_score": 88,
                "verdict": "Verified",
                "recommended_action": "Apply",

                "analysis_summary": "Remote analytics role with transparent hiring process.",
                "risk_level": "Low",

                "flags": [],
                "warnings": [],

                "trust_signals": [
                    "Verified employer",
                    "Public ATS portal"
                ],

                "reasons": [
                    "Strong remote evidence"
                ],

                "evidence": [
                    "Clear compensation and role details"
                ],

                "classification": {
                    "label": "LEGIT_REMOTE"
                },

                "scores": {
                    "remote_authenticity": 90,
                    "legitimacy": 89,
                    "job_quality": 87,
                    "global_eligibility": 86
                },

                "layer_scores": {},

                "country_fit": {
                    "eligible": True
                },

                "company_verification": {
                    "status": "Verified"
                },

                "extracted": {
                    "job_title": "Remote Data Analyst",
                    "company": "Atlas Metrics",
                    "remote_type": "Fully Remote",
                    "apply_url": "https://jobs.greenhouse.io/atlasmetrics/jobs/data-analyst-remote"
                }
            },

            {
                "job_id": "demo-003",
                "applicant_country": "Germany",
                "desired_role": "Backend Engineer",
                "final_score": 90,
                "verdict": "Verified",
                "recommended_action": "Apply",

                "analysis_summary": "Distributed systems backend engineering opportunity.",
                "risk_level": "Low",

                "flags": [],
                "warnings": [],

                "trust_signals": [
                    "Trusted application portal",
                    "Remote infrastructure team"
                ],

                "reasons": [
                    "Strong backend engineering legitimacy"
                ],

                "evidence": [
                    "Verified remote company"
                ],

                "classification": {
                    "label": "LEGIT_REMOTE"
                },

                "scores": {
                    "remote_authenticity": 93,
                    "legitimacy": 91,
                    "job_quality": 89,
                    "global_eligibility": 88
                },

                "layer_scores": {},

                "country_fit": {
                    "eligible": True
                },

                "company_verification": {
                    "status": "Verified"
                },

                "extracted": {
                    "job_title": "Backend Engineer",
                    "company": "RouteForge",
                    "remote_type": "Fully Remote",
                    "apply_url": "https://jobs.lever.co/routeforge/backend-engineer-go"
                }
            }
        ]

        feed.jobs = demo_jobs
        feed.summary.jobs_collected = len(demo_jobs)
        feed.summary.jobs_deduped = len(demo_jobs)
        feed.summary.verified_opportunities = len(demo_jobs)
        feed.summary.risky_jobs_filtered = 0
        feed.summary.average_score = 90
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
