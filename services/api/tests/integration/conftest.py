"""Fixtures for tests that run against a real PostgreSQL database."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from claims_intake import db
from claims_intake.api.deps import document_store_dependency
from claims_intake.config import Settings, get_settings
from claims_intake.main import create_app

API_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql+psycopg://claims:claims@localhost:5432/claims_test"
JWT_SECRET = "integration-test-secret"

# The service resolves its engine from process settings, so the test database is selected
# through the environment before any settings are cached.
os.environ["CLAIMS_DATABASE_URL"] = os.environ.get("CLAIMS_TEST_DATABASE_URL", DEFAULT_DATABASE_URL)
os.environ["CLAIMS_JWT_SECRET"] = JWT_SECRET
os.environ["CLAIMS_AUTH_DISABLED"] = "false"
os.environ["CLAIMS_ENVIRONMENT"] = "test"
get_settings.cache_clear()

TABLES = (
    "audit_event",
    "outbox_entry",
    "idempotency_record",
    "payment_instruction",
    "reserve_entry",
    "claim_document",
    "triage_decision",
    "claim_transition",
    "claim",
)


class StubDocumentStore:
    """In-process stand-in for S3 so tests do not need object storage."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    def presign_upload(self, key: str, content_type: str, ttl: int) -> str:
        self.keys.append(key)
        return f"https://storage.test/upload/{key}?expires={ttl}&type={content_type}"

    def presign_download(self, key: str, ttl: int) -> str:
        return f"https://storage.test/download/{key}?expires={ttl}"

    def healthy(self) -> bool:
        return True


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings: Settings) -> Iterator[None]:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_database(settings: Settings, migrated_database: None) -> Iterator[None]:
    db.reset_engine()
    engine = db.build_engine(settings)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        connection.execute(text("ALTER SEQUENCE claim_reference_seq RESTART WITH 1"))
    engine.dispose()
    yield


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    store = StubDocumentStore()
    app.dependency_overrides[document_store_dependency] = lambda: store
    app.state.stub_document_store = store
    with TestClient(app) as test_client:
        yield test_client


def token_for(*roles: str, subject: str | None = None, name: str = "Test User") -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject or f"user-{uuid.uuid4().hex[:8]}",
            "name": name,
            "roles": list(roles),
            "iss": "https://id.meridian-assurance.example/",
            "aud": "claims-intake-service",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def handler_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('claims_handler')}"}


@pytest.fixture
def senior_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('senior_handler', 'claims_handler')}"}


@pytest.fixture
def auditor_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('auditor')}"}


def fnol_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "policy_reference": "MTR-8891023",
        "product": "MOTOR",
        "peril": "COLLISION",
        "channel": "CONTACT_CENTRE",
        "loss_datetime": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "loss_description": "Rear-ended at a roundabout on the A34, no injuries reported.",
        "estimated_exposure_minor": 180_000,
        "currency": "GBP",
        "policyholder": {
            "full_name": "Aisha Rahman",
            "email": "aisha.rahman@example.com",
            "phone": "+44 7700 900123",
        },
        "incident_location": {
            "line1": "A34 Botley interchange",
            "city": "Oxford",
            "postcode": "OX2 9RS",
            "country": "GB",
        },
        "fraud_indicator": False,
    }
    payload.update(overrides)
    return payload


def register(client: TestClient, auth: dict[str, str], **overrides: Any) -> dict[str, Any]:
    response = client.post("/v1/claims", json=fnol_payload(**overrides), headers=auth)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body
