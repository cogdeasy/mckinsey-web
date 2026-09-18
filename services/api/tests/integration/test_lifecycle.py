"""Lifecycle, triage re-runs and the audit trail (FR-010 to FR-024, FR-060)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import register


def test_fr011_illegal_transition_is_rejected_by_the_api(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    response = client.post(
        f"/v1/claims/{claim['claim_reference']}/transitions",
        json={"target_status": "SETTLED"},
        headers=handler_auth,
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "invalid_transition"
    assert body["details"] == {"from": "TRIAGED", "to": "SETTLED"}


def test_fr012_transitions_are_recorded_on_the_timeline(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    response = client.post(
        f"/v1/claims/{reference}/transitions",
        json={"target_status": "IN_ASSESSMENT", "note": "Assigned to desk"},
        headers=handler_auth,
    )
    assert response.status_code == 201

    timeline = client.get(f"/v1/claims/{reference}/timeline", headers=handler_auth).json()
    kinds = [entry["kind"] for entry in timeline]
    assert "TRANSITION" in kinds
    assert timeline[0]["occurred_at"] <= timeline[-1]["occurred_at"]


def test_fr014_withdrawal_requires_a_reason_code(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    missing = client.post(
        f"/v1/claims/{reference}/transitions",
        json={"target_status": "WITHDRAWN"},
        headers=handler_auth,
    )
    assert missing.status_code == 422

    accepted = client.post(
        f"/v1/claims/{reference}/transitions",
        json={"target_status": "WITHDRAWN", "reason_code": "CUSTOMER_WITHDREW"},
        headers=handler_auth,
    )
    assert accepted.status_code == 201
    assert accepted.json()["to_status"] == "WITHDRAWN"


def test_fr024_rerunning_triage_appends_a_decision(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    response = client.post(f"/v1/claims/{reference}/triage", headers=handler_auth)
    assert response.status_code == 201

    timeline = client.get(f"/v1/claims/{reference}/timeline", headers=handler_auth).json()
    triage_entries = [entry for entry in timeline if entry["kind"] == "TRIAGE"]
    assert len(triage_entries) == 2


def test_fr020_fraud_indicator_routes_to_special_investigation(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth, fraud_indicator=True)
    assert claim["triage"]["segment"] == "SPECIAL_INVESTIGATION"
    assert claim["triage"]["rule_id"] == "fraud-referral"


def test_fr060_audit_events_are_written_for_every_change(
    client: TestClient, handler_auth: dict[str, str], auditor_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    client.post(
        f"/v1/claims/{reference}/transitions",
        json={"target_status": "IN_ASSESSMENT"},
        headers=handler_auth,
    )

    events = client.get(f"/v1/claims/{reference}/audit-events", headers=auditor_auth).json()
    event_types = [event["event_type"] for event in events["items"]]
    assert "claim.registered" in event_types
    assert "claim.status_changed" in event_types
    assert all(event["payload_digest"] for event in events["items"])
