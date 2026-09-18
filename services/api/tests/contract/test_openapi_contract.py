"""Contract tests: the published schema is accurate and stable (FR-092, FR-093)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from claims_intake.config import Settings
from claims_intake.main import create_app

API_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = API_ROOT / "openapi.json"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    app = create_app(Settings(environment="test", auth_disabled=True))
    document: dict[str, Any] = app.openapi()
    return document


def test_committed_snapshot_matches_the_generated_schema(schema: dict[str, Any]) -> None:
    committed = json.loads(SNAPSHOT.read_text())
    assert committed == schema, "Run `make openapi` and commit services/api/openapi.json"


def test_every_documented_path_is_versioned_or_infrastructure(schema: dict[str, Any]) -> None:
    infrastructure = {"/healthz", "/readyz", "/metrics", "/"}
    for path in schema["paths"]:
        assert path.startswith("/v1/") or path in infrastructure, path


def test_bearer_security_is_declared(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]
    assert schemes["bearerAuth"]["scheme"] == "bearer"


def test_write_endpoints_document_the_error_envelope(schema: dict[str, Any]) -> None:
    operation = schema["paths"]["/v1/claims"]["post"]
    for status_code in ("401", "403", "409", "422"):
        content = operation["responses"][status_code]["content"]["application/json"]
        assert content["schema"]["$ref"].endswith("/ErrorResponse")


def test_claim_creation_rejects_unknown_fields(schema: dict[str, Any]) -> None:
    claim_create = schema["components"]["schemas"]["ClaimCreate"]
    assert claim_create["additionalProperties"] is False


def test_idempotency_key_header_is_documented(schema: dict[str, Any]) -> None:
    parameters = schema["paths"]["/v1/claims"]["post"]["parameters"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in parameters)
