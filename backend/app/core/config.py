from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent


class Settings:
    app_name: str = "RemoteTrust AI API"
    app_version: str = "0.1.0"
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    sqlite_path: Path = Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "remote_trust.db")))
    use_openai: bool = os.getenv("OPENAI_API_KEY") is not None
    graph_backend: str = os.getenv("GRAPH_BACKEND", "neo4j").lower()
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "remote-trust-dev")


settings = Settings()
