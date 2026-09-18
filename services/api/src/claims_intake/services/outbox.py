"""Transactional outbox writing and dispatch (FR-070 to FR-072, ADR 0005)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.enums import OutboxState
from ..models import OutboxEntry
from ..observability.logging import get_logger
from ..observability.metrics import OUTBOX_DEAD_LETTERS, OUTBOX_DEPTH, OUTBOX_PUBLISHED

logger = get_logger("claims_intake.outbox")

TOPIC_CLAIM_REGISTERED = "claims.claim.registered"
TOPIC_CLAIM_STATUS_CHANGED = "claims.claim.status_changed"
TOPIC_PAYMENT_INSTRUCTED = "payments.instruction.raised"
TOPIC_CUSTOMER_NOTIFICATION = "communications.customer.notification"

Publisher = Callable[[OutboxEntry], None]


def enqueue(
    session: Session, *, topic: str, payload: dict[str, Any], correlation_id: str
) -> OutboxEntry:
    """Write an entry in the caller's transaction; never publishes inline."""

    entry = OutboxEntry(
        topic=topic,
        payload=payload,
        correlation_id=correlation_id,
        state=OutboxState.PENDING.value,
        attempts=0,
    )
    session.add(entry)
    return entry


def pending_depth(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(OutboxEntry)
            .where(OutboxEntry.state == OutboxState.PENDING.value)
        )
        or 0
    )


def dead_letter_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(OutboxEntry)
            .where(OutboxEntry.state == OutboxState.DEAD_LETTER.value)
        )
        or 0
    )


def refresh_gauges(session: Session) -> None:
    OUTBOX_DEPTH.set(pending_depth(session))
    OUTBOX_DEAD_LETTERS.set(dead_letter_count(session))


def dispatch_batch(
    session: Session, publisher: Publisher, *, batch_size: int, max_attempts: int
) -> int:
    """Publish pending entries at least once, dead-lettering after max_attempts."""

    entries = list(
        session.scalars(
            select(OutboxEntry)
            .where(OutboxEntry.state == OutboxState.PENDING.value)
            .order_by(OutboxEntry.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    published = 0
    for entry in entries:
        try:
            publisher(entry)
        except Exception as exc:  # noqa: BLE001 - dispatch must survive publisher faults
            entry.attempts += 1
            entry.last_error = str(exc)[:1000]
            if entry.attempts >= max_attempts:
                entry.state = OutboxState.DEAD_LETTER.value
                logger.error(
                    "outbox.dead_letter",
                    extra={"outbox_id": str(entry.id), "topic": entry.topic},
                )
            continue
        entry.state = OutboxState.SENT.value
        entry.sent_at = datetime.now(tz=UTC)
        OUTBOX_PUBLISHED.labels(entry.topic).inc()
        published += 1
    refresh_gauges(session)
    return published
