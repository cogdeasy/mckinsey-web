"""Claim orchestration: intake, lifecycle, triage, reserves and settlement."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select, text, tuple_
from sqlalchemy.orm import Session, selectinload

from ..domain import authority, rules, sla
from ..domain.enums import (
    Channel,
    ClaimStatus,
    PaymentState,
    Peril,
    Product,
    ReasonCode,
    ReserveCategory,
    ReserveState,
    Role,
    Segment,
)
from ..domain.reference import format_reference
from ..domain.state_machine import TransitionRequest, assert_transition_allowed
from ..errors import (
    AuthorityExceededError,
    InvalidTransitionError,
    NotFoundError,
    SettlementExceedsReserveError,
    ValidationError,
)
from ..models import (
    Claim,
    ClaimTransition,
    PaymentInstruction,
    ReserveEntry,
    TriageDecisionRecord,
)
from ..observability.metrics import CLAIMS_REGISTERED, TRIAGE_DECISIONS
from ..schemas import ClaimCreate, ReserveCreate, SettlementCreate
from ..security import Principal
from . import audit, outbox

DUPLICATE_WINDOW = timedelta(hours=72)
DEFAULT_PRIORITY = 3
REFERENCE_SEQUENCE = "claim_reference_seq"


@dataclass(frozen=True)
class ReserveOutcome:
    reserve: ReserveEntry
    requires_approval: bool
    authority_limit_minor: int


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def next_claim_reference(session: Session, *, year: int) -> str:
    sequence = session.scalar(text(f"SELECT nextval('{REFERENCE_SEQUENCE}')"))
    return format_reference(year, int(sequence or 1))


def detect_duplicate(session: Session, *, policy_reference: str, loss_datetime: datetime) -> bool:
    """FR-006: same policy and loss notified inside the duplicate window."""

    existing = session.scalar(
        select(func.count())
        .select_from(Claim)
        .where(
            Claim.policy_reference == policy_reference,
            Claim.loss_datetime >= loss_datetime - DUPLICATE_WINDOW,
            Claim.loss_datetime <= loss_datetime + DUPLICATE_WINDOW,
            Claim.status.notin_([ClaimStatus.WITHDRAWN.value, ClaimStatus.REJECTED.value]),
        )
    )
    return bool(existing)


def _record_transition(
    session: Session,
    *,
    claim: Claim,
    target: ClaimStatus,
    principal: Principal,
    correlation_id: str,
    reason_code: ReasonCode | None,
    note: str | None,
) -> ClaimTransition:
    source = ClaimStatus(claim.status)
    assert_transition_allowed(
        TransitionRequest(
            source=source, target=target, roles=principal.roles, reason_code=reason_code
        )
    )
    transition = ClaimTransition(
        claim=claim,
        from_status=source.value,
        to_status=target.value,
        reason_code=reason_code.value if reason_code else None,
        note=note,
        actor_id=principal.subject,
        actor_role=principal.primary_role.value,
        correlation_id=correlation_id,
    )
    session.add(transition)
    claim.status = target.value
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.status_changed",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "from": source.value,
            "to": target.value,
            "reason_code": reason_code.value if reason_code else None,
        },
    )
    outbox.enqueue(
        session,
        topic=outbox.TOPIC_CLAIM_STATUS_CHANGED,
        correlation_id=correlation_id,
        payload={
            "claim_reference": claim.claim_reference,
            "from": source.value,
            "to": target.value,
            "actor_id": principal.subject,
        },
    )
    return transition


def _run_triage(
    session: Session,
    *,
    claim: Claim,
    rule_set: rules.RuleSet,
    now: datetime,
) -> TriageDecisionRecord:
    facts = rules.build_facts(
        product=Product(claim.product),
        peril=Peril(claim.peril),
        estimated_exposure_minor=claim.estimated_exposure_minor,
        fraud_indicator=claim.fraud_indicator,
        duplicate_suspected=claim.duplicate_suspected,
        channel=Channel(claim.channel),
        days_since_loss=max((now - _aware(claim.loss_datetime)).days, 0),
        policyholder_country=claim.incident_country,
    )
    decision = rule_set.evaluate(facts)
    record = TriageDecisionRecord(
        claim=claim,
        segment=decision.outcome.segment.value,
        priority=decision.outcome.priority,
        queue=decision.outcome.queue,
        rule_id=decision.rule_id,
        rule_set_version=decision.rule_set_version,
        facts=facts,
    )
    session.add(record)
    claim.segment = decision.outcome.segment.value
    claim.priority = decision.outcome.priority
    claim.queue = decision.outcome.queue

    targets = sla.targets_for(_aware(claim.reported_at), decision.outcome.segment)
    claim.acknowledgement_due_at = targets.acknowledgement_due_at
    claim.first_contact_due_at = targets.first_contact_due_at
    claim.decision_due_at = targets.decision_due_at

    TRIAGE_DECISIONS.labels(decision.outcome.segment.value, decision.rule_set_version).inc()
    return record


def register_claim(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    payload: ClaimCreate,
    rule_set: rules.RuleSet,
    now: datetime | None = None,
) -> Claim:
    """FR-001 to FR-006 plus the initial triage (FR-020)."""

    principal.require_write()
    moment = now or _now()
    loss_datetime = _aware(payload.loss_datetime)
    if loss_datetime > moment:
        raise ValidationError(
            "The loss datetime cannot be in the future",
            {"loss_datetime": loss_datetime.isoformat()},
        )

    location = payload.incident_location
    claim = Claim(
        claim_reference=next_claim_reference(session, year=moment.year),
        policy_reference=payload.policy_reference,
        product=payload.product.value,
        peril=payload.peril.value,
        channel=payload.channel.value,
        status=ClaimStatus.REGISTERED.value,
        loss_datetime=loss_datetime,
        reported_at=moment,
        loss_description=payload.loss_description,
        estimated_exposure_minor=payload.estimated_exposure_minor,
        currency=payload.currency,
        policyholder_name=payload.policyholder.full_name,
        policyholder_email=str(payload.policyholder.email),
        policyholder_phone=payload.policyholder.phone,
        incident_line1=location.line1 if location else None,
        incident_city=location.city if location else None,
        incident_postcode=location.postcode if location else None,
        incident_country=location.country if location else "GB",
        fraud_indicator=payload.fraud_indicator,
        duplicate_suspected=detect_duplicate(
            session,
            policy_reference=payload.policy_reference,
            loss_datetime=loss_datetime,
        ),
        awaiting_information=False,
    )
    session.add(claim)
    session.flush()

    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.registered",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "policy_reference": claim.policy_reference,
            "product": claim.product,
            "peril": claim.peril,
            "estimated_exposure_minor": claim.estimated_exposure_minor,
            "duplicate_suspected": claim.duplicate_suspected,
        },
    )
    _run_triage(session, claim=claim, rule_set=rule_set, now=moment)
    _record_transition(
        session,
        claim=claim,
        target=ClaimStatus.TRIAGED,
        principal=principal,
        correlation_id=correlation_id,
        reason_code=ReasonCode.TRIAGE_COMPLETE,
        note=None,
    )
    outbox.enqueue(
        session,
        topic=outbox.TOPIC_CLAIM_REGISTERED,
        correlation_id=correlation_id,
        payload={
            "claim_reference": claim.claim_reference,
            "policy_reference": claim.policy_reference,
            "segment": claim.segment,
            "queue": claim.queue,
        },
    )
    outbox.enqueue(
        session,
        topic=outbox.TOPIC_CUSTOMER_NOTIFICATION,
        correlation_id=correlation_id,
        payload={
            "template": "fnol_acknowledgement",
            "claim_reference": claim.claim_reference,
            "recipient": claim.policyholder_email,
        },
    )
    CLAIMS_REGISTERED.labels(claim.product, claim.channel).inc()
    session.flush()
    return claim


def get_claim(session: Session, claim_reference: str, *, with_detail: bool = False) -> Claim:
    statement: Select[tuple[Claim]] = select(Claim).where(Claim.claim_reference == claim_reference)
    if with_detail:
        statement = statement.options(
            selectinload(Claim.reserves),
            selectinload(Claim.documents),
            selectinload(Claim.payments),
            selectinload(Claim.transitions),
            selectinload(Claim.triage_decisions),
        )
    claim = session.scalar(statement)
    if claim is None:
        raise NotFoundError(
            f"No claim exists with reference {claim_reference}",
            {"claim_reference": claim_reference},
        )
    return claim


def encode_cursor(claim: Claim) -> str:
    raw = json.dumps(
        {
            "priority": claim.priority or DEFAULT_PRIORITY,
            "reported_at": _aware(claim.reported_at).isoformat(),
            "id": str(claim.id),
        }
    )
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[int, datetime, uuid.UUID]:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        return (
            int(raw["priority"]),
            datetime.fromisoformat(raw["reported_at"]),
            uuid.UUID(raw["id"]),
        )
    except Exception as exc:
        raise ValidationError("The pagination cursor is not valid", {"cursor": cursor}) from exc


def list_claims(
    session: Session,
    *,
    limit: int,
    cursor: str | None = None,
    status: ClaimStatus | None = None,
    segment: Segment | None = None,
    queue: str | None = None,
    policy_reference: str | None = None,
    breached: bool | None = None,
    now: datetime | None = None,
) -> tuple[Sequence[Claim], str | None]:
    """Queue listing, ordered by priority then age, keyset paginated (FR-090)."""

    moment = now or _now()
    priority_key = func.coalesce(Claim.priority, DEFAULT_PRIORITY)
    statement = select(Claim).order_by(priority_key, Claim.reported_at, Claim.id).limit(limit + 1)

    if status is not None:
        statement = statement.where(Claim.status == status.value)
    if segment is not None:
        statement = statement.where(Claim.segment == segment.value)
    if queue is not None:
        statement = statement.where(Claim.queue == queue)
    if policy_reference is not None:
        statement = statement.where(Claim.policy_reference == policy_reference)
    if breached is True:
        statement = statement.where(
            Claim.awaiting_information.is_(False), Claim.decision_due_at < moment
        )
    elif breached is False:
        statement = statement.where(
            (Claim.awaiting_information.is_(True)) | (Claim.decision_due_at >= moment)
        )
    if cursor:
        priority, reported_at, claim_id = decode_cursor(cursor)
        statement = statement.where(
            tuple_(priority_key, Claim.reported_at, Claim.id) > (priority, reported_at, claim_id)
        )

    claims = list(session.scalars(statement))
    if len(claims) > limit:
        return claims[:limit], encode_cursor(claims[limit - 1])
    return claims, None


def apply_transition(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    target: ClaimStatus,
    reason_code: ReasonCode | None,
    note: str | None,
) -> ClaimTransition:
    principal.require_write()
    return _record_transition(
        session,
        claim=claim,
        target=target,
        principal=principal,
        correlation_id=correlation_id,
        reason_code=reason_code,
        note=note,
    )


def rerun_triage(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    rule_set: rules.RuleSet,
    now: datetime | None = None,
) -> TriageDecisionRecord:
    """FR-024: a re-run adds a decision, it never overwrites one."""

    principal.require_write()
    record = _run_triage(session, claim=claim, rule_set=rule_set, now=now or _now())
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.triaged",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "segment": record.segment,
            "priority": record.priority,
            "queue": record.queue,
            "rule_id": record.rule_id,
            "rule_set_version": record.rule_set_version,
        },
    )
    session.flush()
    return record


def approved_reserve_minor(claim: Claim, category: ReserveCategory) -> int:
    approved = [
        entry
        for entry in claim.reserves
        if entry.category == category.value and entry.state == ReserveState.APPROVED.value
    ]
    if not approved:
        return 0
    latest = max(approved, key=lambda entry: entry.created_at)
    return latest.amount_minor


def settled_minor(claim: Claim) -> int:
    return sum(
        payment.amount_minor
        for payment in claim.payments
        if payment.state != PaymentState.FAILED.value
    )


def propose_reserve(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    payload: ReserveCreate,
) -> ReserveOutcome:
    """FR-040 to FR-042."""

    principal.require_write()
    if claim.currency != payload.currency:
        raise ValidationError(
            "A reserve must use the claim currency",
            {"claim_currency": claim.currency, "supplied": payload.currency},
        )
    if ClaimStatus(claim.status) in {
        ClaimStatus.SETTLED,
        ClaimStatus.REJECTED,
        ClaimStatus.WITHDRAWN,
        ClaimStatus.CLOSED,
    }:
        raise InvalidTransitionError(
            f"A reserve cannot be changed on a {claim.status} claim",
            {"status": claim.status},
        )

    decision = authority.evaluate(payload.amount_minor, principal.roles)
    if decision.escalate_to_technical_desk:
        claim.queue = authority.TECHNICAL_DESK_QUEUE
        claim.segment = Segment.COMPLEX.value

    if ClaimStatus(claim.status) is ClaimStatus.TRIAGED:
        _record_transition(
            session,
            claim=claim,
            target=ClaimStatus.IN_ASSESSMENT,
            principal=principal,
            correlation_id=correlation_id,
            reason_code=ReasonCode.ASSESSMENT_STARTED,
            note=None,
        )

    state = ReserveState.APPROVED if decision.within_authority else ReserveState.PROPOSED
    entry = ReserveEntry(
        claim=claim,
        category=payload.category.value,
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        state=state.value,
        note=payload.note,
        actor_id=principal.subject,
        actor_role=principal.primary_role.value,
        decided_by=principal.subject if decision.within_authority else None,
        decided_at=_now() if decision.within_authority else None,
    )
    session.add(entry)

    if not decision.within_authority:
        claim.pending_amount_minor = payload.amount_minor
        claim.pending_kind = "RESERVE"
        if ClaimStatus(claim.status) is ClaimStatus.IN_ASSESSMENT:
            _record_transition(
                session,
                claim=claim,
                target=ClaimStatus.PENDING_APPROVAL,
                principal=principal,
                correlation_id=correlation_id,
                reason_code=ReasonCode.APPROVAL_REQUESTED,
                note=payload.note,
            )

    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.reserve_changed",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "category": entry.category,
            "amount_minor": entry.amount_minor,
            "state": entry.state,
            "authority_limit_minor": decision.limit_minor,
        },
    )
    session.flush()
    return ReserveOutcome(
        reserve=entry,
        requires_approval=not decision.within_authority,
        authority_limit_minor=decision.limit_minor,
    )


def decide_approval(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    approve: bool,
    note: str,
) -> ReserveEntry:
    """FR-043: senior handler approves or declines the pending amount."""

    principal.require_senior()
    if ClaimStatus(claim.status) is not ClaimStatus.PENDING_APPROVAL:
        raise InvalidTransitionError(
            "There is no pending approval on this claim", {"status": claim.status}
        )
    proposals = [entry for entry in claim.reserves if entry.state == ReserveState.PROPOSED.value]
    if not proposals:
        raise NotFoundError("There is no proposed reserve awaiting a decision")
    proposal = max(proposals, key=lambda entry: entry.created_at)

    proposal.state = (ReserveState.APPROVED if approve else ReserveState.DECLINED).value
    proposal.decided_by = principal.subject
    proposal.decided_at = _now()
    proposal.note = note

    claim.pending_amount_minor = None
    claim.pending_kind = None
    _record_transition(
        session,
        claim=claim,
        target=ClaimStatus.APPROVED if approve else ClaimStatus.IN_ASSESSMENT,
        principal=principal,
        correlation_id=correlation_id,
        reason_code=ReasonCode.APPROVAL_GRANTED if approve else ReasonCode.APPROVAL_DECLINED,
        note=note,
    )
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.approval_decided",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "approved": approve,
            "amount_minor": proposal.amount_minor,
            "reserve_id": str(proposal.id),
        },
    )
    session.flush()
    return proposal


def settle(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    payload: SettlementCreate,
) -> PaymentInstruction:
    """FR-044, FR-045 and the outbox write that reaches the payments hub (FR-070)."""

    principal.require_senior()
    if ClaimStatus(claim.status) is not ClaimStatus.APPROVED:
        raise InvalidTransitionError(
            "A settlement may only be raised on an approved claim", {"status": claim.status}
        )
    if payload.currency != claim.currency:
        raise ValidationError(
            "A settlement must use the claim currency",
            {"claim_currency": claim.currency, "supplied": payload.currency},
        )

    decision = authority.evaluate(payload.amount_minor, principal.roles)
    if not decision.within_authority:
        raise AuthorityExceededError(
            "The settlement amount exceeds the senior handler authority limit",
            {"limit_minor": decision.limit_minor, "amount_minor": payload.amount_minor},
        )

    reserve = approved_reserve_minor(claim, ReserveCategory.INDEMNITY)
    already_settled = settled_minor(claim)
    if already_settled + payload.amount_minor > reserve:
        raise SettlementExceedsReserveError(
            "The settlement would exceed the approved indemnity reserve",
            {
                "approved_reserve_minor": reserve,
                "already_settled_minor": already_settled,
                "requested_minor": payload.amount_minor,
            },
        )

    instruction = PaymentInstruction(
        claim=claim,
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        payee_name=payload.payee_name,
        payee_reference=payload.payee_reference,
        state=PaymentState.INSTRUCTED.value,
        instructed_by=principal.subject,
    )
    session.add(instruction)
    session.flush()

    _record_transition(
        session,
        claim=claim,
        target=ClaimStatus.SETTLED,
        principal=principal,
        correlation_id=correlation_id,
        reason_code=ReasonCode.SETTLEMENT_ISSUED,
        note=payload.note,
    )
    outbox.enqueue(
        session,
        topic=outbox.TOPIC_PAYMENT_INSTRUCTED,
        correlation_id=correlation_id,
        payload={
            "payment_instruction_id": str(instruction.id),
            "claim_reference": claim.claim_reference,
            "amount_minor": instruction.amount_minor,
            "currency": instruction.currency,
            "payee_name": instruction.payee_name,
            "payee_reference": instruction.payee_reference,
        },
    )
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.settled",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "amount_minor": instruction.amount_minor,
            "payment_instruction_id": str(instruction.id),
        },
    )
    session.flush()
    return instruction


def role_can_read_all(principal: Principal) -> bool:
    """FR-062: auditors see every claim regardless of queue ownership."""

    return Role.AUDITOR in principal.roles


def triage_facts_snapshot(claim: Claim) -> dict[str, Any]:
    if not claim.triage_decisions:
        return {}
    latest = max(claim.triage_decisions, key=lambda record: record.created_at)
    return dict(latest.facts)
