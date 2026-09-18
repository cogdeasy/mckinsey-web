"""Documents, health and readiness (FR-030 to FR-033, NFR-006)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from .conftest import register


def upload_ticket(
    client: TestClient, auth: dict[str, str], reference: str, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "filename": "engineer-report.pdf",
        "content_type": "application/pdf",
        "size_bytes": 482_133,
        "kind": "ESTIMATE",
    }
    payload.update(overrides)
    response = client.post(f"/v1/claims/{reference}/documents", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_fr030_upload_then_confirm_makes_the_document_available(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    reference = register(client, handler_auth)["claim_reference"]
    ticket = upload_ticket(client, handler_auth, reference)
    assert str(ticket["upload_url"]).startswith("https://storage.test/upload/")
    document_id = ticket["document"]["id"]

    confirm = client.post(
        f"/v1/claims/{reference}/documents/{document_id}/confirm",
        json={"checksum_sha256": "a" * 64},
        headers=handler_auth,
    )
    assert confirm.status_code == 200
    assert confirm.json()["state"] == "AVAILABLE"

    listed = client.get(f"/v1/claims/{reference}/documents", headers=handler_auth).json()
    assert len(listed) == 1


def test_fr032_unsupported_content_type_is_rejected(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    reference = register(client, handler_auth)["claim_reference"]
    response = client.post(
        f"/v1/claims/{reference}/documents",
        json={
            "filename": "dashcam.mp4",
            "content_type": "video/mp4",
            "size_bytes": 1_000,
            "kind": "OTHER",
        },
        headers=handler_auth,
    )
    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


def test_fr033_download_url_is_time_limited(
    client: TestClient, handler_auth: dict[str, str], auditor_auth: dict[str, str]
) -> None:
    reference = register(client, handler_auth)["claim_reference"]
    ticket = upload_ticket(client, handler_auth, reference)
    document_id = ticket["document"]["id"]
    client.post(
        f"/v1/claims/{reference}/documents/{document_id}/confirm",
        json={"checksum_sha256": "b" * 64},
        headers=handler_auth,
    )

    response = client.get(
        f"/v1/claims/{reference}/documents/{document_id}/download-url", headers=auditor_auth
    )
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in_seconds"] > 0
    assert str(body["download_url"]).startswith("https://storage.test/download/")


def test_nfr006_health_and_readiness(client: TestClient) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] is True


def test_nfr005_metrics_are_exposed(client: TestClient, handler_auth: dict[str, str]) -> None:
    register(client, handler_auth)
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "claims_registered_total" in metrics.text


def test_nfr004_correlation_id_is_echoed(client: TestClient, handler_auth: dict[str, str]) -> None:
    response = client.get("/v1/claims", headers={**handler_auth, "X-Correlation-Id": "corr-test-1"})
    assert response.headers["X-Correlation-Id"] == "corr-test-1"


def test_not_found_uses_the_error_envelope(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    response = client.get("/v1/claims/MER-2026-999999", headers=handler_auth)
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"code", "message", "details", "correlation_id"}
    assert body["code"] == "not_found"
