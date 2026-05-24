from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

try:  # Installed through requirements; optional at import time for clearer errors.
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

from app.core.config import PROJECT_ROOT, settings
from app.db.database import get_job, insert_job, list_jobs
from app.models import (
    AnalyzeRequest,
    IngestionQueueRequest,
    IngestionQueueResponse,
    IngestionRunSummary,
    IngestionStatusResponse,
    OpportunityFeedResponse,
    OpportunityFeedSummary,
)
from app.services.analyzer import analyze
from app.services.job_fetcher import JobFetchError, fetch_job_description
from ml.feature_extractor import clean_job_text, extract_apply_url, extract_features


_run_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def project_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def configured_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else settings.lakehouse_path.parent.parent / value


def lakehouse_root() -> Path:
    settings.lakehouse_path.mkdir(parents=True, exist_ok=True)
    return settings.lakehouse_path


def queue_path() -> Path:
    path = lakehouse_root() / "queue" / "url_queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def duckdb_error() -> RuntimeError:
    return RuntimeError("DuckDB is required for ingestion. Install backend requirements before running the lakehouse pipeline.")


def connect_lakehouse():
    if duckdb is None:
        raise duckdb_error()
    root = lakehouse_root()
    return duckdb.connect(str(root / "remote_trust_lakehouse.duckdb"))


def init_lakehouse(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze_job_events (
            record_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            source_name VARCHAR,
            source_type VARCHAR,
            source_url VARCHAR,
            job_url VARCHAR,
            applicant_country VARCHAR,
            desired_role VARCHAR,
            raw_title VARCHAR,
            raw_company VARCHAR,
            raw_description VARCHAR,
            raw_payload_json VARCHAR,
            collected_at VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS silver_job_postings (
            fingerprint VARCHAR PRIMARY KEY,
            bronze_record_id VARCHAR,
            source_name VARCHAR,
            source_type VARCHAR,
            job_url VARCHAR,
            apply_url VARCHAR,
            applicant_country VARCHAR,
            desired_role VARCHAR,
            job_title VARCHAR,
            company VARCHAR,
            location VARCHAR,
            remote_type VARCHAR,
            cleaned_description VARCHAR,
            preprocessing_warnings_json VARCHAR,
            created_at VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS gold_opportunities (
            fingerprint VARCHAR PRIMARY KEY,
            job_id VARCHAR,
            curation_bucket VARCHAR,
            published_to_feed BOOLEAN,
            final_score INTEGER,
            verdict VARCHAR,
            recommended_action VARCHAR,
            classification_label VARCHAR,
            apply_url VARCHAR,
            evidence_summary VARCHAR,
            processed_at VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id VARCHAR PRIMARY KEY,
            status VARCHAR,
            started_at VARCHAR,
            completed_at VARCHAR,
            source_records_collected INTEGER,
            bronze_records_written INTEGER,
            silver_records_created INTEGER,
            duplicates_skipped INTEGER,
            gold_records_published INTEGER,
            verified_opportunities INTEGER,
            risky_jobs_filtered INTEGER,
            errors_json VARCHAR
        )
        """
    )


def valid_http_url(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def source_config() -> dict[str, Any]:
    if settings.ingestion_source_config.exists():
        return json.loads(settings.ingestion_source_config.read_text(encoding="utf-8"))
    return {
        "file_sources": [
            {
                "name": "sample_jobs",
                "path": "data/sample_jobs.json",
                "enabled": True,
                "default_applicant_country": "India",
            }
        ],
        "feed_sources": [],
    }


def source_file_path(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def bronze_record(
    *,
    run_id: str,
    source_name: str,
    source_type: str,
    source_url: str | None,
    payload: dict[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    job_url = valid_http_url(payload.get("job_url") or payload.get("url"))
    return {
        "record_id": str(uuid.uuid4()),
        "run_id": run_id,
        "source_name": source_name,
        "source_type": source_type,
        "source_url": source_url,
        "job_url": job_url,
        "applicant_country": payload.get("applicant_country") or payload.get("default_applicant_country") or "India",
        "desired_role": payload.get("desired_role") or payload.get("role") or payload.get("category"),
        "raw_title": payload.get("job_title") or payload.get("title") or payload.get("name"),
        "raw_company": payload.get("company") or payload.get("company_name"),
        "raw_description": payload.get("job_description") or payload.get("description") or "",
        "raw_payload_json": json_dumps(payload),
        "collected_at": collected_at,
    }


def collect_file_source(run_id: str, source: dict[str, Any], collected_at: str, errors: list[str]) -> list[dict[str, Any]]:
    if not source.get("enabled", True):
        return []
    path_value = source.get("path")
    if not path_value:
        return []
    path = source_file_path(str(path_value))
    if not path.exists():
        errors.append(f"Source file not found: {path}")
        return []

    records: list[dict[str, Any]] = []
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data.get("jobs", data) if isinstance(data, dict) else data
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = {
                **row,
                "default_applicant_country": source.get("default_applicant_country", "India"),
            }
            records.append(
                bronze_record(
                    run_id=run_id,
                    source_name=str(source.get("name") or path.stem),
                    source_type="file",
                    source_url=str(path),
                    payload=payload,
                    collected_at=collected_at,
                )
            )
    except Exception as exc:
        errors.append(f"Could not collect file source {path}: {exc}")
    return records


def remotive_description(job: dict[str, Any]) -> str:
    parts = [
        f"Company: {job.get('company_name')}" if job.get("company_name") else None,
        f"Job Title: {job.get('title')}" if job.get("title") else None,
        f"Location: {job.get('candidate_required_location')}" if job.get("candidate_required_location") else None,
        f"Salary: {job.get('salary')}" if job.get("salary") else None,
        normalize_text(job.get("description")),
        f"Apply at {job.get('url')}" if job.get("url") else None,
    ]
    return "\n".join(part for part in parts if part)


def collect_feed_source(run_id: str, source: dict[str, Any], collected_at: str, errors: list[str]) -> list[dict[str, Any]]:
    if not source.get("enabled", True):
        return []
    if httpx is None:
        errors.append("httpx is required for feed ingestion.")
        return []
    source_type = str(source.get("type") or "").lower()
    source_url = source.get("url")
    if source_type != "remotive" or not source_url:
        errors.append(f"Unsupported feed source: {source.get('name') or source_type or 'unknown'}")
        return []
    try:
        with httpx.Client(timeout=float(source.get("timeout_seconds", 8)), follow_redirects=True) as client:
            response = client.get(str(source_url))
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        errors.append(f"Could not collect feed {source.get('name') or source_url}: {exc}")
        return []

    records: list[dict[str, Any]] = []
    limit = int(source.get("limit", 20))
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    for job in jobs[:limit]:
        if not isinstance(job, dict):
            continue
        normalized = {
            "job_url": job.get("url"),
            "job_title": job.get("title"),
            "company": job.get("company_name"),
            "job_description": remotive_description(job),
            "applicant_country": source.get("applicant_country", "India"),
            "desired_role": source.get("desired_role") or job.get("category"),
            "raw_feed_job": job,
        }
        records.append(
            bronze_record(
                run_id=run_id,
                source_name=str(source.get("name") or "remotive"),
                source_type="feed",
                source_url=str(source_url),
                payload=normalized,
                collected_at=collected_at,
            )
        )
    return records


def collect_url_queue(run_id: str, collected_at: str, errors: list[str]) -> list[dict[str, Any]]:
    path = queue_path()
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            errors.append("A URL queue line could not be parsed.")
            continue
        records.append(
            bronze_record(
                run_id=run_id,
                source_name="url_queue",
                source_type="url_queue",
                source_url=str(path),
                payload=payload,
                collected_at=collected_at,
            )
        )
    return records


def collect_bronze_records(run_id: str, collected_at: str, errors: list[str]) -> list[dict[str, Any]]:
    config = source_config()
    records: list[dict[str, Any]] = []
    for source in config.get("file_sources", []):
        if isinstance(source, dict):
            records.extend(collect_file_source(run_id, source, collected_at, errors))
    for source in config.get("feed_sources", []):
        if isinstance(source, dict):
            records.extend(collect_feed_source(run_id, source, collected_at, errors))
    records.extend(collect_url_queue(run_id, collected_at, errors))
    return records


def insert_bronze(connection: Any, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    connection.executemany(
        """
        INSERT OR IGNORE INTO bronze_job_events (
            record_id, run_id, source_name, source_type, source_url, job_url,
            applicant_country, desired_role, raw_title, raw_company, raw_description,
            raw_payload_json, collected_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                record["record_id"],
                record["run_id"],
                record["source_name"],
                record["source_type"],
                record["source_url"],
                record["job_url"],
                record["applicant_country"],
                record["desired_role"],
                record["raw_title"],
                record["raw_company"],
                record["raw_description"],
                record["raw_payload_json"],
                record["collected_at"],
            )
            for record in records
        ],
    )
    return len(records)


def fingerprint_for(job_url: str | None, applicant_country: str, desired_role: str | None, text: str) -> str:
    basis = job_url or re.sub(r"\s+", " ", text[:800].lower())
    value = f"{basis}|{applicant_country.lower()}|{(desired_role or '').lower()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def existing_silver_fingerprints(connection: Any) -> set[str]:
    return {row[0] for row in connection.execute("SELECT fingerprint FROM silver_job_postings").fetchall()}


def silver_from_bronze(records: list[dict[str, Any]], existing: set[str], errors: list[str]) -> tuple[list[dict[str, Any]], int]:
    silver: list[dict[str, Any]] = []
    duplicates = 0
    for record in records:
        warnings: list[str] = []
        job_url = valid_http_url(record.get("job_url"))
        raw_description = normalize_text(record.get("raw_description"))
        if not raw_description and job_url:
            try:
                fetched = fetch_job_description(job_url)
                raw_description = fetched.text
                if fetched.warning:
                    warnings.append(fetched.warning)
            except JobFetchError as exc:
                warnings.append(str(exc))

        cleaned = clean_job_text(raw_description)
        fingerprint = fingerprint_for(job_url, record["applicant_country"], record.get("desired_role"), cleaned)
        if fingerprint in existing:
            duplicates += 1
            continue

        extracted = extract_features(cleaned, job_url) if cleaned else None
        if extracted:
            warnings.extend(extracted.extraction_warnings)
        apply_url = valid_http_url(extract_apply_url(cleaned, job_url) if cleaned else None) or job_url

        if len(cleaned) < 80:
            warnings.append("Not enough readable job text for a reliable trust analysis.")
        if not apply_url:
            warnings.append("No application URL was detected.")

        silver.append(
            {
                "fingerprint": fingerprint,
                "bronze_record_id": record["record_id"],
                "source_name": record["source_name"],
                "source_type": record["source_type"],
                "job_url": job_url,
                "apply_url": apply_url,
                "applicant_country": record["applicant_country"],
                "desired_role": record.get("desired_role"),
                "job_title": extracted.job_title if extracted else record.get("raw_title"),
                "company": extracted.company if extracted else record.get("raw_company"),
                "location": extracted.location if extracted else None,
                "remote_type": extracted.remote_type if extracted else None,
                "cleaned_description": cleaned,
                "preprocessing_warnings_json": json_dumps(list(dict.fromkeys(warnings))),
                "created_at": utc_now(),
            }
        )
        existing.add(fingerprint)
    return silver, duplicates


def insert_silver(connection: Any, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    connection.executemany(
        """
        INSERT OR IGNORE INTO silver_job_postings (
            fingerprint, bronze_record_id, source_name, source_type, job_url, apply_url,
            applicant_country, desired_role, job_title, company, location, remote_type,
            cleaned_description, preprocessing_warnings_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                record["fingerprint"],
                record["bronze_record_id"],
                record["source_name"],
                record["source_type"],
                record["job_url"],
                record["apply_url"],
                record["applicant_country"],
                record["desired_role"],
                record["job_title"],
                record["company"],
                record["location"],
                record["remote_type"],
                record["cleaned_description"],
                record["preprocessing_warnings_json"],
                record["created_at"],
            )
            for record in records
        ],
    )
    return len(records)


def pending_silver_records(connection: Any) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM silver_job_postings
        WHERE fingerprint NOT IN (SELECT fingerprint FROM gold_opportunities)
        ORDER BY created_at ASC
        """
    ).fetchall()
    columns = [item[0] for item in connection.description]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def curation_bucket_for(final_score: int, verdict: str, recommended_action: str, classification_label: str) -> str:
    if recommended_action == "Apply" or (final_score >= 80 and classification_label == "LEGIT_REMOTE"):
        return "curated"
    if verdict == "Risky" or recommended_action == "Avoid" or classification_label in {"LIKELY_SCAM", "HYBRID_OR_LOCATION_BOUND"}:
        return "rejected"
    return "review"


def evidence_summary(response: Any) -> str:
    for item in [*response.positive_signals, *response.red_flags]:
        if item:
            return item
    return response.explanation[:220]


def insert_gold(connection: Any, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    connection.executemany(
        """
        INSERT OR IGNORE INTO gold_opportunities (
            fingerprint, job_id, curation_bucket, published_to_feed, final_score,
            verdict, recommended_action, classification_label, apply_url,
            evidence_summary, processed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                record["fingerprint"],
                record["job_id"],
                record["curation_bucket"],
                record["published_to_feed"],
                record["final_score"],
                record["verdict"],
                record["recommended_action"],
                record["classification_label"],
                record["apply_url"],
                record["evidence_summary"],
                record["processed_at"],
            )
            for record in records
        ],
    )
    return len(records)


def analyze_silver_records(records: list[dict[str, Any]], errors: list[str]) -> list[dict[str, Any]]:
    gold: list[dict[str, Any]] = []
    for record in records:
        description = record.get("cleaned_description") or ""
        if len(description) < 20:
            errors.append(f"Skipped {record['fingerprint'][:10]}: not enough readable job text.")
            continue
        request = AnalyzeRequest(
            job_url=record.get("job_url"),
            job_description=description,
            applicant_country=record.get("applicant_country") or "India",
            desired_role=record.get("desired_role"),
        )
        try:
            response = analyze(request)
            if record.get("apply_url") and not response.extracted.apply_url:
                response.extracted.apply_url = record["apply_url"]
            saved = insert_job(request, response, source_fingerprint=record["fingerprint"])
        except Exception as exc:
            errors.append(f"Could not analyze {record['fingerprint'][:10]}: {exc}")
            continue

        label = response.classification.label
        bucket = curation_bucket_for(response.final_score, response.verdict, response.recommended_action, label)
        gold.append(
            {
                "fingerprint": record["fingerprint"],
                "job_id": saved.job_id,
                "curation_bucket": bucket,
                "published_to_feed": True,
                "final_score": saved.final_score,
                "verdict": saved.verdict,
                "recommended_action": saved.recommended_action,
                "classification_label": label,
                "apply_url": saved.extracted.apply_url or saved.job_url or record.get("apply_url"),
                "evidence_summary": evidence_summary(saved),
                "processed_at": utc_now(),
            }
        )
    return gold


def export_parquet_snapshots(connection: Any, errors: list[str]) -> None:
    root = lakehouse_root()
    exports = {
        "bronze_job_events": root / "bronze" / "job_events.parquet",
        "silver_job_postings": root / "silver" / "job_postings.parquet",
        "gold_opportunities": root / "gold" / "opportunities.parquet",
        "ingestion_runs": root / "runs" / "ingestion_runs.parquet",
    }
    for table, path in exports.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path).replace("\\", "/").replace("'", "''")
        try:
            connection.execute(f"COPY (SELECT * FROM {table}) TO '{target}' (FORMAT PARQUET)")
        except Exception as exc:
            errors.append(f"Could not export {table} to Parquet: {exc}")


def count_query(connection: Any, sql: str) -> int:
    return int(connection.execute(sql).fetchone()[0] or 0)


def count_verified_jobs(connection: Any) -> int:
    return count_query(
        connection,
        """
        SELECT COUNT(*)
        FROM gold_opportunities
        WHERE curation_bucket = 'curated'
        """,
    )


def count_risky_jobs(connection: Any) -> int:
    return count_query(
        connection,
        """
        SELECT COUNT(*)
        FROM gold_opportunities
        WHERE curation_bucket = 'rejected'
        """,
    )


def insert_run_summary(connection: Any, summary: IngestionRunSummary) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO ingestion_runs (
            run_id, status, started_at, completed_at, source_records_collected,
            bronze_records_written, silver_records_created, duplicates_skipped,
            gold_records_published, verified_opportunities, risky_jobs_filtered,
            errors_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            summary.run_id,
            summary.status,
            summary.started_at,
            summary.completed_at,
            summary.source_records_collected,
            summary.bronze_records_written,
            summary.silver_records_created,
            summary.duplicates_skipped,
            summary.gold_records_published,
            summary.verified_opportunities,
            summary.risky_jobs_filtered,
            json_dumps(summary.errors),
        ),
    )


def run_ingestion() -> IngestionRunSummary:
    run_id = str(uuid.uuid4())
    started_at = utc_now()
    errors: list[str] = []
    if not _run_lock.acquire(blocking=False):
        return IngestionRunSummary(
            run_id=run_id,
            status="already_running",
            started_at=started_at,
            completed_at=utc_now(),
            errors=["Another ingestion run is already active."],
            lakehouse_path=str(lakehouse_root()),
        )

    try:
        connection = connect_lakehouse()
        try:
            init_lakehouse(connection)
            bronze = collect_bronze_records(run_id, started_at, errors)
            bronze_written = insert_bronze(connection, bronze)
            silver, duplicates = silver_from_bronze(bronze, existing_silver_fingerprints(connection), errors)
            silver_created = insert_silver(connection, silver)
            pending = pending_silver_records(connection)
            gold = analyze_silver_records(pending, errors)
            gold_published = insert_gold(connection, gold)
            export_parquet_snapshots(connection, errors)

            summary = IngestionRunSummary(
                run_id=run_id,
                status="completed_with_warnings" if errors else "completed",
                started_at=started_at,
                completed_at=utc_now(),
                source_records_collected=len(bronze),
                bronze_records_written=bronze_written,
                silver_records_created=silver_created,
                duplicates_skipped=duplicates,
                gold_records_published=gold_published,
                verified_opportunities=count_verified_jobs(connection),
                risky_jobs_filtered=count_risky_jobs(connection),
                errors=errors,
                lakehouse_path=str(lakehouse_root()),
            )
            insert_run_summary(connection, summary)
            return summary
        finally:
            connection.close()
    except Exception as exc:
        errors.append(str(exc))
        return IngestionRunSummary(
            run_id=run_id,
            status="failed",
            started_at=started_at,
            completed_at=utc_now(),
            errors=errors,
            lakehouse_path=str(lakehouse_root()),
        )
    finally:
        _run_lock.release()


def last_run_row(connection: Any) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM ingestion_runs
        ORDER BY completed_at DESC NULLS LAST, started_at DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    columns = [item[0] for item in connection.description]
    return dict(zip(columns, row, strict=True))


def ingestion_status() -> IngestionStatusResponse:
    if duckdb is None:
        return IngestionStatusResponse(
            scheduler_enabled=settings.ingestion_enabled,
            interval_seconds=settings.ingestion_interval_seconds,
            is_running=_run_lock.locked(),
            last_status="duckdb_unavailable",
            last_error="DuckDB is not installed.",
            lakehouse_path=str(lakehouse_root()),
        )
    try:
        connection = connect_lakehouse()
        try:
            init_lakehouse(connection)
            row = last_run_row(connection)
        finally:
            connection.close()
    except Exception as exc:
        return IngestionStatusResponse(
            scheduler_enabled=settings.ingestion_enabled,
            interval_seconds=settings.ingestion_interval_seconds,
            is_running=_run_lock.locked(),
            last_status="unavailable",
            last_error=str(exc),
            lakehouse_path=str(lakehouse_root()),
        )
    errors = json.loads(row["errors_json"]) if row and row.get("errors_json") else []
    return IngestionStatusResponse(
        scheduler_enabled=settings.ingestion_enabled,
        interval_seconds=settings.ingestion_interval_seconds,
        is_running=_run_lock.locked(),
        last_run_at=row.get("completed_at") if row else None,
        last_status=row.get("status") if row else "not_run",
        last_error=errors[0] if errors else None,
        lakehouse_path=str(lakehouse_root()),
    )


def lakehouse_counts() -> dict[str, int]:
    if duckdb is None:
        return {"jobs_collected": 0, "jobs_deduped": 0, "verified_opportunities": 0, "risky_jobs_filtered": 0}
    try:
        connection = connect_lakehouse()
        try:
            init_lakehouse(connection)
            return {
                "jobs_collected": count_query(connection, "SELECT COUNT(*) FROM bronze_job_events"),
                "jobs_deduped": count_query(connection, "SELECT COUNT(*) FROM silver_job_postings"),
                "verified_opportunities": count_verified_jobs(connection),
                "risky_jobs_filtered": count_risky_jobs(connection),
            }
        finally:
            connection.close()
    except Exception:
        return {"jobs_collected": 0, "jobs_deduped": 0, "verified_opportunities": 0, "risky_jobs_filtered": 0}


def gold_job_ids() -> list[str]:
    if duckdb is None:
        return []
    try:
        connection = connect_lakehouse()
        try:
            init_lakehouse(connection)
            rows = connection.execute(
                """
                SELECT job_id
                FROM gold_opportunities
                WHERE published_to_feed = true
                ORDER BY processed_at DESC
                """
            ).fetchall()
        finally:
            connection.close()
    except Exception:
        return []
    return [row[0] for row in rows]


def opportunity_jobs() -> list[Any]:
    ids = gold_job_ids()
    if not ids:
        return list_jobs()
    jobs = [get_job(job_id) for job_id in ids]
    return [job for job in jobs if job]


def opportunity_feed() -> OpportunityFeedResponse:
    jobs = opportunity_jobs()
    counts = lakehouse_counts()
    status = ingestion_status()
    average_score = round(sum(job.final_score for job in jobs) / len(jobs)) if jobs else None
    return OpportunityFeedResponse(
        summary=OpportunityFeedSummary(
            scheduler_enabled=status.scheduler_enabled,
            ingestion_status=status.last_status,
            last_run_at=status.last_run_at,
            jobs_collected=counts["jobs_collected"],
            jobs_deduped=counts["jobs_deduped"],
            verified_opportunities=counts["verified_opportunities"],
            risky_jobs_filtered=counts["risky_jobs_filtered"],
            average_score=average_score,
            lakehouse_path=status.lakehouse_path,
        ),
        jobs=jobs,
    )


def enqueue_url(payload: IngestionQueueRequest) -> IngestionQueueResponse:
    url = valid_http_url(payload.job_url)
    if not url:
        raise ValueError("Provide a valid http or https job URL.")
    path = queue_path()
    record = {
        "job_url": url,
        "applicant_country": payload.applicant_country,
        "desired_role": payload.desired_role,
        "queued_at": utc_now(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json_dumps(record) + "\n")
    queued_count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return IngestionQueueResponse(
        queued=True,
        queued_count=queued_count,
        message="URL queued for the next ingestion run.",
    )
