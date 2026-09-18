"""Runtime configuration, loaded from the environment (12-factor, NFR-007)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RULE_SET = Path(__file__).resolve().parent / "rules" / "triage.yaml"


class Settings(BaseSettings):
    """Service configuration. No secret has a usable default."""

    model_config = SettingsConfigDict(env_prefix="CLAIMS_", env_file=".env", extra="ignore")

    environment: str = "local"
    service_name: str = "claims-intake-service"

    database_url: str = "postgresql+psycopg://claims:claims@localhost:5432/claims"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    jwt_secret: str = "local-development-only"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "https://id.meridian-assurance.example/"
    jwt_audience: str = "claims-intake-service"
    auth_disabled: bool = False

    documents_bucket: str = "meridian-claim-documents"
    s3_endpoint_url: str | None = None
    s3_region: str = "eu-west-2"
    presign_upload_ttl_seconds: int = 900
    presign_download_ttl_seconds: int = 300
    max_document_bytes: int = 25 * 1024 * 1024

    rule_set_path: Path = DEFAULT_RULE_SET

    otel_exporter_otlp_endpoint: str | None = None
    log_level: str = "INFO"

    outbox_batch_size: int = Field(default=50, ge=1, le=500)
    outbox_max_attempts: int = Field(default=5, ge=1, le=20)
    outbox_poll_seconds: float = Field(default=2.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
