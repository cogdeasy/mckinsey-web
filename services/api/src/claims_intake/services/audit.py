"""Audit event writing (FR-060 to FR-062)."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..security import Principal


def digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    event_type: str,
    payload: dict[str, Any],
    claim_id: uuid.UUID | None = None,
    claim_reference: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        claim_id=claim_id,
        claim_reference=claim_reference,
        event_type=event_type,
        actor_id=principal.subject,
        actor_role=principal.primary_role.value,
        correlation_id=correlation_id,
        payload=payload,
        payload_digest=digest(payload),
    )
    session.add(event)
    return event
