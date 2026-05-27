from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings
from app.db.database import list_jobs, reset_db
from app.models import IngestionQueueRequest
from app.services.job_fetcher import FetchResult
from app.services.ingestion import enqueue_url, opportunity_feed, run_ingestion, source_file_path


def configure_ingestion(tmp_path: Path) -> None:
    settings.sqlite_path = tmp_path / "remote_trust.db"
    settings.lakehouse_path = tmp_path / "lakehouse"
    settings.ingestion_source_config = tmp_path / "ingestion_sources.json"
    settings.graph_backend = "sqlite"
    os.environ["WEB_VERIFICATION_ENABLED"] = "false"
    reset_db()


def write_source(tmp_path: Path) -> Path:
    source_path = tmp_path / "jobs.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "applicant_country": "India",
                    "desired_role": "Software Engineer",
                    "job_url": "https://jobs.greenhouse.io/northstarlabs/jobs/remote-senior-software-engineer",
                    "job_description": """
                    Company: Northstar Labs
                    Job Title: Senior Software Engineer
                    Location: Remote worldwide
                    Northstar Labs is a remote-first distributed team building collaboration tools.
                    Global applicants are welcome and contractor arrangements are supported.
                    Salary: USD $120,000-$160,000.
                    Responsibilities include building Python APIs, maintaining services, and collaborating with product.
                    Required skills: Python, TypeScript, SQL, Docker.
                    Interview process: recruiter screen, technical interview, team interview.
                    Apply at https://jobs.greenhouse.io/northstarlabs/jobs/remote-senior-software-engineer
                    """,
                },
                {
                    "applicant_country": "India",
                    "desired_role": "Software Engineer",
                    "job_url": "https://jobs.greenhouse.io/northstarlabs/jobs/remote-senior-software-engineer",
                    "job_description": "Duplicate should be deduped by URL, country, and role.",
                },
                {
                    "applicant_country": "Philippines",
                    "desired_role": "Data Entry",
                    "job_url": None,
                    "job_description": """
                    Job Title: Remote Data Entry Assistant
                    Earn $500/day from home. No interview required. You must send money for
                    an equipment fee by wire transfer before onboarding. Contact us on Telegram only.
                    """,
                },
            ]
        ),
        encoding="utf-8",
    )
    settings.ingestion_source_config.write_text(
        json.dumps(
            {
                "file_sources": [
                    {
                        "name": "test_jobs",
                        "path": str(source_path),
                        "enabled": True,
                    }
                ],
                "feed_sources": [],
            }
        ),
        encoding="utf-8",
    )
    return source_path


def test_lakehouse_ingestion_layers_dedupe_and_publish(tmp_path: Path) -> None:
    configure_ingestion(tmp_path)
    write_source(tmp_path)

    first = run_ingestion()
    second = run_ingestion()
    feed = opportunity_feed()

    assert first.bronze_records_written == 3
    assert first.silver_records_created == 1
    assert first.preprocessing_rejected == 1
    assert first.gold_records_published == 1
    assert second.duplicates_skipped == 3
    assert second.gold_records_published == 0
    assert len(list_jobs()) == 1
    assert feed.summary.jobs_collected == 6
    assert feed.summary.jobs_deduped == 1
    assert feed.summary.opportunities_available == len(feed.jobs)
    assert feed.summary.preprocessing_rejected == 1
    assert feed.summary.verified_opportunities >= 1
    assert feed.summary.risky_jobs_filtered >= 1
    assert (settings.lakehouse_path / "bronze" / "job_events.parquet").exists()
    assert (settings.lakehouse_path / "silver" / "job_postings.parquet").exists()
    assert (settings.lakehouse_path / "silver" / "rejected_job_postings.parquet").exists()
    assert (settings.lakehouse_path / "gold" / "opportunities.parquet").exists()
    assert any(job.extracted.apply_url for job in feed.jobs)


def test_url_queue_adds_live_collection_input_and_drains_after_processing(tmp_path: Path, monkeypatch) -> None:
    configure_ingestion(tmp_path)
    settings.ingestion_source_config.write_text(json.dumps({"file_sources": [], "feed_sources": []}), encoding="utf-8")

    def fake_fetch_job_description(_url: str) -> FetchResult:
        return FetchResult(
            text="""
            Company: QueueCloud
            Job Title: Backend Engineer
            Location: Remote worldwide
            QueueCloud is a remote-first distributed team building workflow software.
            Global applicants are welcome and contractor arrangements are supported.
            Salary: USD $115,000-$145,000.
            Responsibilities include building Python APIs, maintaining PostgreSQL services,
            collaborating with product, and improving production reliability.
            Required skills: Python, TypeScript, SQL, Docker, API design.
            Benefits include paid time off, home office budget, and learning stipend.
            Interview process: recruiter screen, technical interview, team interview.
            Apply at https://jobs.lever.co/example/backend-engineer
            """,
            source="test fixture",
        )

    monkeypatch.setattr("app.services.ingestion.fetch_job_description", fake_fetch_job_description)

    response = enqueue_url(
        IngestionQueueRequest(
            job_url="https://jobs.lever.co/example/backend-engineer",
            applicant_country="Canada",
            desired_role="Backend Engineer",
        )
    )

    assert response.queued
    assert response.queued_count == 1
    queue_file = settings.lakehouse_path / "queue" / "url_queue.jsonl"
    assert queue_file.exists()

    result = run_ingestion()
    feed = opportunity_feed()

    assert result.gold_records_published == 1
    assert queue_file.read_text(encoding="utf-8") == ""
    assert feed.summary.opportunities_available == 1


def test_deployed_data_mount_source_path_falls_back_to_packaged_data() -> None:
    resolved = source_file_path("/data/sample_jobs.json")

    assert resolved.exists()
    assert resolved.name == "sample_jobs.json"
