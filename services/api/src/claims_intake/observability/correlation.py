"""Correlation identifier propagated through logs, audit events and the outbox."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

CORRELATION_HEADER = "X-Correlation-Id"

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def current_correlation_id() -> str:
    value = correlation_id_var.get()
    return value or new_correlation_id()
