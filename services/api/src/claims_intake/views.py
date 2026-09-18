"""Projections from persistence models onto API models."""

from __future__ import annotations

from datetime import UTC, datetime

from .domain import rules, sla
from .domain.enums import ReserveCategory
from .models import AuditEvent, Claim, ClaimDocument, ReserveEntry, TriageDecisionRecord
from .schemas import (
    Address,
    AuditEventView,
    ClaimDetail,
    ClaimSummary,
    DocumentView,
    PaymentView,
    Policyholder,
    ReserveView,
    RuleOutcomeView,
    RuleSetView,
    RuleView,
    SlaView,
    TimelineEntry,
    TransitionView,
    TriageView,
)
from .services.claims import approved_reserve_minor, settled_minor


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _latest_triage(claim: Claim) -> TriageDecisionRecord | None:
    if not claim.triage_decisions:
        return None
    return max(claim.triage_decisions, key=lambda record: record.created_at)


def sla_view(claim: Claim, now: datetime | None = None) -> SlaView:
    moment = now or datetime.now(tz=UTC)
    due = _aware(claim.decision_due_at) if claim.decision_due_at else None
    return SlaView(
        acknowledgement_due_at=claim.acknowledgement_due_at,
        first_contact_due_at=claim.first_contact_due_at,
        decision_due_at=claim.decision_due_at,
        awaiting_information=claim.awaiting_information,
        breached=sla.is_breached(due, moment, claim.awaiting_information),
    )


def triage_view(record: TriageDecisionRecord) -> TriageView:
    return TriageView(
        segment=record.segment,
        priority=record.priority,
        queue=record.queue,
        rule_id=record.rule_id,
        rule_set_version=record.rule_set_version,
        decided_at=record.created_at,
    )


def reserve_view(entry: ReserveEntry) -> ReserveView:
    return ReserveView.model_validate(entry)


def document_view(document: ClaimDocument) -> DocumentView:
    return DocumentView.model_validate(document)


def claim_summary(claim: Claim, now: datetime | None = None) -> ClaimSummary:
    return ClaimSummary(
        claim_reference=claim.claim_reference,
        policy_reference=claim.policy_reference,
        product=claim.product,
        peril=claim.peril,
        status=claim.status,
        segment=claim.segment,
        priority=claim.priority,
        queue=claim.queue,
        policyholder_name=claim.policyholder_name,
        estimated_exposure_minor=claim.estimated_exposure_minor,
        currency=claim.currency,
        duplicate_suspected=claim.duplicate_suspected,
        reported_at=claim.reported_at,
        sla=sla_view(claim, now),
    )


def claim_detail(claim: Claim, now: datetime | None = None) -> ClaimDetail:
    triage = _latest_triage(claim)
    summary = claim_summary(claim, now)
    location = None
    if claim.incident_line1 or claim.incident_city or claim.incident_postcode:
        location = Address(
            line1=claim.incident_line1,
            city=claim.incident_city,
            postcode=claim.incident_postcode,
            country=claim.incident_country,
        )
    return ClaimDetail(
        **summary.model_dump(),
        id=claim.id,
        channel=claim.channel,
        loss_datetime=claim.loss_datetime,
        loss_description=claim.loss_description,
        fraud_indicator=claim.fraud_indicator,
        incident_location=location,
        policyholder=Policyholder(
            full_name=claim.policyholder_name,
            email=claim.policyholder_email,
            phone=claim.policyholder_phone,
        ),
        triage=triage_view(triage) if triage else None,
        reserves=[reserve_view(entry) for entry in claim.reserves],
        documents=[document_view(document) for document in claim.documents],
        payments=[PaymentView.model_validate(payment) for payment in claim.payments],
        indemnity_reserve_minor=approved_reserve_minor(claim, ReserveCategory.INDEMNITY),
        settled_minor=settled_minor(claim),
        pending_amount_minor=claim.pending_amount_minor,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def transition_view(transition: object) -> TransitionView:
    return TransitionView.model_validate(transition)


def audit_event_view(event: AuditEvent) -> AuditEventView:
    return AuditEventView.model_validate(event)


def timeline(claim: Claim) -> list[TimelineEntry]:
    """Merge lifecycle, triage, reserve, document and payment events (FR-101)."""

    entries: list[TimelineEntry] = []
    for transition in claim.transitions:
        entries.append(
            TimelineEntry(
                occurred_at=transition.created_at,
                kind="TRANSITION",
                summary=f"{transition.from_status or 'NEW'} to {transition.to_status}",
                actor_id=transition.actor_id,
                detail={
                    "reason_code": transition.reason_code,
                    "note": transition.note,
                    "correlation_id": transition.correlation_id,
                },
            )
        )
    for decision in claim.triage_decisions:
        entries.append(
            TimelineEntry(
                occurred_at=decision.created_at,
                kind="TRIAGE",
                summary=f"Triaged as {decision.segment} to queue {decision.queue}",
                actor_id="system",
                detail={
                    "rule_id": decision.rule_id,
                    "rule_set_version": decision.rule_set_version,
                    "priority": decision.priority,
                },
            )
        )
    for reserve in claim.reserves:
        entries.append(
            TimelineEntry(
                occurred_at=reserve.created_at,
                kind="RESERVE",
                summary=(
                    f"{reserve.category} reserve {reserve.state.lower()} at "
                    f"{reserve.amount_minor} {reserve.currency} minor units"
                ),
                actor_id=reserve.actor_id,
                detail={
                    "category": reserve.category,
                    "amount_minor": reserve.amount_minor,
                    "state": reserve.state,
                    "decided_by": reserve.decided_by,
                },
            )
        )
    for document in claim.documents:
        entries.append(
            TimelineEntry(
                occurred_at=document.confirmed_at or document.created_at,
                kind="DOCUMENT",
                summary=f"Document {document.filename} ({document.kind.lower()})",
                actor_id=document.uploaded_by,
                detail={"state": document.state, "size_bytes": document.size_bytes},
            )
        )
    for payment in claim.payments:
        entries.append(
            TimelineEntry(
                occurred_at=payment.created_at,
                kind="PAYMENT",
                summary=(
                    f"Payment instruction {payment.amount_minor} {payment.currency} "
                    f"minor units to {payment.payee_name}"
                ),
                actor_id=payment.instructed_by,
                detail={"state": payment.state, "payee_reference": payment.payee_reference},
            )
        )
    return sorted(entries, key=lambda entry: _aware(entry.occurred_at))


def rule_set_view(rule_set: rules.RuleSet) -> RuleSetView:
    return RuleSetView(
        version=rule_set.version,
        rules=[
            RuleView(
                id=rule.rule_id,
                description=rule.description,
                when={fact: dict(predicate) for fact, predicate in rule.conditions.items()},
                then=RuleOutcomeView(
                    segment=rule.outcome.segment,
                    priority=rule.outcome.priority,
                    queue=rule.outcome.queue,
                ),
            )
            for rule in rule_set.rules
        ],
        default=RuleOutcomeView(
            segment=rule_set.default.segment,
            priority=rule_set.default.priority,
            queue=rule_set.default.queue,
        ),
    )
