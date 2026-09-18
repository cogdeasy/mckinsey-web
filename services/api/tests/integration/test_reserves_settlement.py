"""Reserves, approvals, settlement and the outbox (FR-040 to FR-045, FR-070)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from claims_intake import db
from claims_intake.models import OutboxEntry

from .conftest import register


def escalate_and_approve(
    client: TestClient,
    handler_auth: dict[str, str],
    senior_auth: dict[str, str],
    *,
    amount_minor: int,
) -> str:
    claim = register(client, handler_auth, estimated_exposure_minor=amount_minor)
    reference = claim["claim_reference"]
    reserve = client.post(
        f"/v1/claims/{reference}/reserves",
        json={"category": "INDEMNITY", "amount_minor": amount_minor, "currency": "GBP"},
        headers=handler_auth,
    )
    assert reserve.status_code == 201, reserve.text
    assert reserve.json()["requires_approval"] is True

    approval = client.post(
        f"/v1/claims/{reference}/approvals",
        json={"decision": "APPROVE", "note": "Engineer report supports the figure"},
        headers=senior_auth,
    )
    assert approval.status_code == 201, approval.text
    return str(reference)


def test_fr041_reserve_within_authority_is_set_immediately(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    response = client.post(
        f"/v1/claims/{reference}/reserves",
        json={"amount_minor": 120_000, "note": "Bodyshop estimate"},
        headers=handler_auth,
    )
    body = response.json()
    assert response.status_code == 201
    assert body["requires_approval"] is False
    assert body["reserve"]["state"] == "APPROVED"
    assert body["claim_status"] == "IN_ASSESSMENT"


def test_fr042_reserve_above_authority_moves_to_pending_approval(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    response = client.post(
        f"/v1/claims/{reference}/reserves",
        json={"amount_minor": 900_000},
        headers=handler_auth,
    )
    body = response.json()
    assert body["requires_approval"] is True
    assert body["claim_status"] == "PENDING_APPROVAL"
    assert body["authority_limit_minor"] == 250_000


def test_fr043_only_a_senior_handler_can_approve(
    client: TestClient, handler_auth: dict[str, str]
) -> None:
    claim = register(client, handler_auth)
    reference = claim["claim_reference"]
    client.post(
        f"/v1/claims/{reference}/reserves", json={"amount_minor": 900_000}, headers=handler_auth
    )
    response = client.post(
        f"/v1/claims/{reference}/approvals",
        json={"decision": "APPROVE", "note": "Within my own authority"},
        headers=handler_auth,
    )
    assert response.status_code == 403


def test_fr044_settlement_is_capped_by_the_approved_reserve(
    client: TestClient, handler_auth: dict[str, str], senior_auth: dict[str, str]
) -> None:
    reference = escalate_and_approve(client, handler_auth, senior_auth, amount_minor=900_000)
    over = client.post(
        f"/v1/claims/{reference}/settlements",
        json={
            "amount_minor": 1_000_000,
            "currency": "GBP",
            "payee_name": "Oxford Bodyworks Ltd",
            "payee_reference": "SUP-4471",
        },
        headers=senior_auth,
    )
    assert over.status_code == 409
    assert over.json()["code"] == "settlement_exceeds_reserve"


def test_fr045_settlement_closes_the_claim_and_raises_a_payment_message(
    client: TestClient, handler_auth: dict[str, str], senior_auth: dict[str, str]
) -> None:
    reference = escalate_and_approve(client, handler_auth, senior_auth, amount_minor=900_000)
    response = client.post(
        f"/v1/claims/{reference}/settlements",
        json={
            "amount_minor": 900_000,
            "currency": "GBP",
            "payee_name": "Oxford Bodyworks Ltd",
            "payee_reference": "SUP-4471",
        },
        headers=senior_auth,
    )
    assert response.status_code == 201, response.text

    claim = client.get(f"/v1/claims/{reference}", headers=senior_auth).json()
    assert claim["status"] == "SETTLED"
    assert claim["settled_minor"] == 900_000

    with db.session_scope() as session:
        topics = list(session.scalars(select(OutboxEntry.topic).order_by(OutboxEntry.created_at)))
    assert "payments.instruction.raised" in topics
    assert "claims.claim.registered" in topics
