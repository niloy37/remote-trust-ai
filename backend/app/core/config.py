from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def env_path(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else PROJECT_ROOT / value


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
    ingestion_enabled: bool = env_bool("INGESTION_ENABLED", True)
    ingestion_interval_seconds: int = int(os.getenv("INGESTION_INTERVAL_SECONDS", "300"))
    lakehouse_path: Path = env_path("LAKEHOUSE_PATH", "data/lakehouse")
    ingestion_source_config: Path = env_path("INGESTION_SOURCE_CONFIG", "data/ingestion_sources.json")


settings = Settings()
