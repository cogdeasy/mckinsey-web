"""Intake, duplicate detection and idempotency against PostgreSQL (FR-001 to FR-006)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from .conftest import fnol_payload, register


def test_fr001_fnol_is_registered_and_triaged(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    assert claim["claim_reference"].startswith("MER-")
    assert claim["status"] == "TRIAGED"
    assert claim["triage"]["queue"]
    assert claim["sla"]["decision_due_at"] is not None


def test_fr003_references_are_sequential(client: TestClient, handler_auth: dict[str, str]) -> None:
    first = register(client, handler_auth)
    second = register(client, handler_auth, policy_reference="MTR-8891024")
    year = datetime.now(UTC).year
    assert first["claim_reference"] == f"MER-{year}-000001"
    assert second["claim_reference"] == f"MER-{year}-000002"


def test_fr002_future_loss_date_is_rejected(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    response = client.post(
        "/v1/claims",
        json=fnol_payload(loss_datetime=(datetime.now(UTC) + timedelta(days=1)).isoformat()),
        headers=handler_auth,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["correlation_id"]


def test_fr006_duplicate_within_72_hours_is_flagged(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    loss = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    first = register(client, handler_auth, loss_datetime=loss)
    second = register(client, handler_auth, loss_datetime=loss)
    assert first["duplicate_suspected"] is False
    assert second["duplicate_suspected"] is True


def test_fr004_idempotent_replay_returns_the_first_response(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    headers = {**handler_auth, "Idempotency-Key": "fnol-6f1a"}
    payload = fnol_payload()
    first = client.post("/v1/claims", json=payload, headers=headers)
    second = client.post("/v1/claims", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.headers["Idempotent-Replay"] == "true"
    assert first.json()["claim_reference"] == second.json()["claim_reference"]

    listed = client.get("/v1/claims", headers=headers)
    assert len(listed.json()["items"]) == 1


def test_fr005_reusing_a_key_with_a_different_body_conflicts(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    headers = {**handler_auth, "Idempotency-Key": "fnol-9c2b"}
    client.post("/v1/claims", json=fnol_payload(), headers=headers)
    response = client.post(
        "/v1/claims", json=fnol_payload(estimated_exposure_minor=999_000), headers=headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_key_reuse"


def test_fr090_queue_pagination_and_filters(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    for index in range(5):
        register(client, handler_auth, policy_reference=f"MTR-889100{index}")

    first_page = client.get("/v1/claims", params={"limit": 2}, headers=handler_auth).json()
    assert len(first_page["items"]) == 2
    assert first_page["next_cursor"]

    second_page = client.get(
        "/v1/claims",
        params={"limit": 2, "cursor": first_page["next_cursor"]},
        headers=handler_auth,
    ).json()
    assert len(second_page["items"]) == 2
    first_refs = {item["claim_reference"] for item in first_page["items"]}
    second_refs = {item["claim_reference"] for item in second_page["items"]}
    assert first_refs.isdisjoint(second_refs)

    filtered = client.get(
        "/v1/claims", params={"policy_reference": "MTR-8891002"}, headers=handler_auth
    ).json()
    assert len(filtered["items"]) == 1


def test_fr080_requests_without_a_token_are_rejected(client: TestClient) -> None:
    response = client.get("/v1/claims")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_fr081_a_forged_token_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/claims", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_fr082_auditor_cannot_write(client: TestClient, auditor_auth: dict[str, str]) -> None:
    response = client.post("/v1/claims", json=fnol_payload(), headers=auditor_auth)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
