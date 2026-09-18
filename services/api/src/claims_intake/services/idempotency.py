"""Idempotency-Key handling for write endpoints (FR-004, FR-005)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import IdempotencyKeyReuseError
from ..models import IdempotencyRecord


def request_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


def find_replay(
    session: Session, *, key: str | None, endpoint: str, payload: Any
) -> StoredResponse | None:
    """Return the stored response for a replay, or raise if the body differs."""

    if not key:
        return None
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.endpoint == endpoint,
        )
    )
    if record is None:
        return None
    if record.request_digest != request_digest(payload):
        raise IdempotencyKeyReuseError(
            "This Idempotency-Key was already used with a different request body",
            {"idempotency_key": key, "endpoint": endpoint},
        )
    return StoredResponse(status_code=record.response_status, body=record.response_body)


def store(
    session: Session,
    *,
    key: str | None,
    endpoint: str,
    payload: Any,
    status_code: int,
    body: dict[str, Any],
) -> None:
    if not key:
        return
    session.add(
        IdempotencyRecord(
            idempotency_key=key,
            endpoint=endpoint,
            request_digest=request_digest(payload),
            response_status=status_code,
            response_body=body,
        )
    )
