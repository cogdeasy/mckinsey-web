"""Persistence model. Money is stored in integer minor units (ADR 0002)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid_column() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Claim(TimestampMixin, Base):
    __tablename__ = "claim"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_reference: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    policy_reference: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(16), nullable=False)
    peril: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)

    loss_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    loss_description: Mapped[str] = mapped_column(Text, nullable=False)

    estimated_exposure_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    policyholder_name: Mapped[str] = mapped_column(String(160), nullable=False)
    policyholder_email: Mapped[str] = mapped_column(String(320), nullable=False)
    policyholder_phone: Mapped[str | None] = mapped_column(String(32))

    incident_line1: Mapped[str | None] = mapped_column(String(160))
    incident_city: Mapped[str | None] = mapped_column(String(80))
    incident_postcode: Mapped[str | None] = mapped_column(String(16))
    incident_country: Mapped[str] = mapped_column(String(2), nullable=False, default="GB")

    fraud_indicator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_suspected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    awaiting_information: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    segment: Mapped[str | None] = mapped_column(String(24), index=True)
    priority: Mapped[int | None] = mapped_column(Integer)
    queue: Mapped[str | None] = mapped_column(String(48), index=True)

    acknowledgement_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_contact_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pending_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    pending_kind: Mapped[str | None] = mapped_column(String(24))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    transitions: Mapped[list[ClaimTransition]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimTransition.created_at"
    )
    triage_decisions: Mapped[list[TriageDecisionRecord]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="TriageDecisionRecord.created_at",
    )
    reserves: Mapped[list[ReserveEntry]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ReserveEntry.created_at"
    )
    documents: Mapped[list[ClaimDocument]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimDocument.created_at"
    )
    payments: Mapped[list[PaymentInstruction]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="PaymentInstruction.created_at",
    )

    __table_args__ = (
        Index("ix_claim_policy_loss", "policy_reference", "loss_datetime"),
        Index("ix_claim_queue_priority", "queue", "priority"),
    )


class ClaimTransition(TimestampMixin, Base):
    """Immutable record of a lifecycle change (FR-012)."""

    __tablename__ = "claim_transition"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)

    claim: Mapped[Claim] = relationship(back_populates="transitions")


class TriageDecisionRecord(TimestampMixin, Base):
    """One row per triage evaluation; never updated (FR-024)."""

    __tablename__ = "triage_decision"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    queue: Mapped[str] = mapped_column(String(48), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(16), nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    claim: Mapped[Claim] = relationship(back_populates="triage_decisions")


class ReserveEntry(TimestampMixin, Base):
    """Append-only reserve history (FR-040)."""

    __tablename__ = "reserve_entry"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    claim: Mapped[Claim] = relationship(back_populates="reserves")


class ClaimDocument(TimestampMixin, Base):
    __tablename__ = "claim_document"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    claim: Mapped[Claim] = relationship(back_populates="documents")


class PaymentInstruction(TimestampMixin, Base):
    __tablename__ = "payment_instruction"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payee_name: Mapped[str] = mapped_column(String(160), nullable=False)
    payee_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    instructed_by: Mapped[str] = mapped_column(String(64), nullable=False)

    claim: Mapped[Claim] = relationship(back_populates="payments")


class AuditEvent(TimestampMixin, Base):
    """Immutable audit trail (FR-060 to FR-062). Never updated or deleted by the API."""

    __tablename__ = "audit_event"

    id: Mapped[uuid.UUID] = _uuid_column()
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claim.id", ondelete="CASCADE"), index=True
    )
    claim_reference: Mapped[str | None] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class OutboxEntry(TimestampMixin, Base):
    """Transactional outbox (FR-070 to FR-072, ADR 0005)."""

    __tablename__ = "outbox_entry"

    id: Mapped[uuid.UUID] = _uuid_column()
    topic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    """Stored responses for replayed write requests (FR-004, FR-005)."""

    __tablename__ = "idempotency_record"

    id: Mapped[uuid.UUID] = _uuid_column()
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", "endpoint", name="uq_idempotency_key_endpoint"),
    )
