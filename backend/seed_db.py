from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import init_db, insert_job, reset_db  # noqa: E402
from app.models import AnalyzeRequest  # noqa: E402
from app.services.analyzer import analyze  # noqa: E402


def seed(reset: bool = False) -> None:
    if reset:
        reset_db()
    else:
        init_db()

    data_path = PROJECT_ROOT / "data" / "sample_jobs.json"
    samples = json.loads(data_path.read_text(encoding="utf-8"))
    for sample in samples:
        request = AnalyzeRequest(
            job_url=sample.get("job_url"),
            job_description=sample["job_description"],
            applicant_country=sample.get("applicant_country", "India"),
            desired_role=sample.get("desired_role"),
        )
        response = analyze(request)
        record = insert_job(request, response)
        print(f"Seeded {record.extracted.job_title or 'Untitled'} -> {record.final_score} ({record.verdict})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RemoteTrust AI with sample analyzed jobs.")
    parser.add_argument("--reset", action="store_true", help="Delete the local SQLite database before seeding.")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()

