"""Claim intake, lifecycle, triage, reserves and settlement endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from ..domain.enums import ClaimStatus, Segment
from ..models import AuditEvent
from ..schemas import (
    ApprovalCreate,
    AuditEventView,
    ClaimCreate,
    ClaimDetail,
    ClaimSummary,
    Page,
    PaymentView,
    ReserveCreate,
    ReserveResult,
    ReserveView,
    SettlementCreate,
    TimelineEntry,
    TransitionCreate,
    TransitionView,
    TriageView,
)
from ..services import claims as claims_service
from ..views import (
    audit_event_view,
    claim_detail,
    claim_summary,
    reserve_view,
    timeline,
    transition_view,
    triage_view,
)
from .deps import (
    CorrelationDep,
    IdempotencyDep,
    PrincipalDep,
    RuleSetDep,
    SessionDep,
)
from .responses import ERROR_RESPONSES, persisted, replayed

router = APIRouter(prefix="/v1/claims", tags=["claims"], responses=ERROR_RESPONSES)


@router.post(
    "",
    response_model=ClaimDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Register a first notification of loss",
    description="Implements FR-001 to FR-006 and runs triage (FR-020).",
)
def register_claim(
    payload: ClaimCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    rule_set: RuleSetDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = "POST /v1/claims"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.register_claim(
        session,
        principal=principal,
        correlation_id=correlation_id,
        payload=payload,
        rule_set=rule_set,
    )
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=claim_detail(claim),
    )


@router.get(
    "",
    response_model=Page[ClaimSummary],
    summary="List claims in queue order",
    description="Cursor paginated queue listing (FR-090, FR-100).",
)
def list_claims(
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
    claim_status: Annotated[ClaimStatus | None, Query(alias="status")] = None,
    segment: Annotated[Segment | None, Query()] = None,
    queue: Annotated[str | None, Query(max_length=48)] = None,
    policy_reference: Annotated[str | None, Query(max_length=32)] = None,
    breached: Annotated[bool | None, Query()] = None,
) -> Page[ClaimSummary]:
    items, next_cursor = claims_service.list_claims(
        session,
        limit=limit,
        cursor=cursor,
        status=claim_status,
        segment=segment,
        queue=queue,
        policy_reference=policy_reference,
        breached=breached,
    )
    return Page[ClaimSummary](
        items=[claim_summary(claim) for claim in items], next_cursor=next_cursor
    )


@router.get(
    "/{claim_reference}",
    response_model=ClaimDetail,
    summary="Read a claim",
    description="Claim detail including triage decision, reserves and documents (FR-101).",
)
def read_claim(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
) -> ClaimDetail:
    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    return claim_detail(claim)


@router.get(
    "/{claim_reference}/timeline",
    response_model=list[TimelineEntry],
    summary="Read the claim timeline",
)
def read_timeline(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
) -> list[TimelineEntry]:
    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    return timeline(claim)


@router.post(
    "/{claim_reference}/transitions",
    response_model=TransitionView,
    status_code=status.HTTP_201_CREATED,
    summary="Apply a lifecycle transition",
    description="Rejects illegal transitions (FR-011) and requires reason codes (FR-014).",
)
def create_transition(
    claim_reference: str,
    payload: TransitionCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = f"POST /v1/claims/{claim_reference}/transitions"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.get_claim(session, claim_reference)
    transition = claims_service.apply_transition(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        target=payload.target_status,
        reason_code=payload.reason_code,
        note=payload.note,
    )
    session.flush()
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=transition_view(transition),
    )


@router.post(
    "/{claim_reference}/triage",
    response_model=TriageView,
    status_code=status.HTTP_201_CREATED,
    summary="Re-run triage",
    description="Creates a new decision rather than overwriting the previous one (FR-024).",
)
def rerun_triage(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    rule_set: RuleSetDep,
) -> TriageView:
    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    record = claims_service.rerun_triage(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        rule_set=rule_set,
    )
    return triage_view(record)


@router.get(
    "/{claim_reference}/reserves",
    response_model=list[ReserveView],
    summary="Read the reserve history",
)
def list_reserves(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
) -> list[ReserveView]:
    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    return [reserve_view(entry) for entry in claim.reserves]


@router.post(
    "/{claim_reference}/reserves",
    response_model=ReserveResult,
    status_code=status.HTTP_201_CREATED,
    summary="Propose or set a reserve",
    description="Applies role authority limits (FR-041, FR-042).",
)
def create_reserve(
    claim_reference: str,
    payload: ReserveCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = f"POST /v1/claims/{claim_reference}/reserves"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    outcome = claims_service.propose_reserve(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        payload=payload,
    )
    result = ReserveResult(
        reserve=reserve_view(outcome.reserve),
        claim_status=ClaimStatus(claim.status),
        requires_approval=outcome.requires_approval,
        authority_limit_minor=outcome.authority_limit_minor,
    )
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=result,
    )


@router.post(
    "/{claim_reference}/approvals",
    response_model=ReserveView,
    status_code=status.HTTP_201_CREATED,
    summary="Approve or decline a pending amount",
    description="Senior handler only (FR-043).",
)
def create_approval(
    claim_reference: str,
    payload: ApprovalCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = f"POST /v1/claims/{claim_reference}/approvals"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    reserve = claims_service.decide_approval(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        approve=payload.decision == "APPROVE",
        note=payload.note,
    )
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=reserve_view(reserve),
    )


@router.post(
    "/{claim_reference}/settlements",
    response_model=PaymentView,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a settlement payment instruction",
    description="Senior handler only; bounded by the approved indemnity reserve (FR-044, FR-045).",
)
def create_settlement(
    claim_reference: str,
    payload: SettlementCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = f"POST /v1/claims/{claim_reference}/settlements"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    instruction = claims_service.settle(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        payload=payload,
    )
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=PaymentView.model_validate(instruction),
    )


@router.get(
    "/{claim_reference}/audit-events",
    response_model=Page[AuditEventView],
    summary="Read the audit trail for a claim",
    description="Read-only, append-only evidence for second line (FR-060 to FR-062).",
)
def list_audit_events(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[AuditEventView]:
    claim = claims_service.get_claim(session, claim_reference)
    events = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.claim_id == claim.id)
            .order_by(AuditEvent.created_at)
            .limit(limit)
        )
    )
    return Page[AuditEventView](items=[audit_event_view(event) for event in events])
