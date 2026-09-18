"""Structured error envelope shared by every endpoint (FR-091)."""

from __future__ import annotations

from typing import Any


class ClaimsError(Exception):
    """Base class for errors that map onto the documented error envelope."""

    code = "internal_error"
    status_code = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class NotFoundError(ClaimsError):
    code = "not_found"
    status_code = 404


class ValidationError(ClaimsError):
    code = "validation_error"
    status_code = 422


class UnauthorizedError(ClaimsError):
    code = "unauthorized"
    status_code = 401


class ForbiddenError(ClaimsError):
    code = "forbidden"
    status_code = 403


class InvalidTransitionError(ClaimsError):
    code = "invalid_transition"
    status_code = 409


class IdempotencyKeyReuseError(ClaimsError):
    code = "idempotency_key_reuse"
    status_code = 409


class AuthorityExceededError(ClaimsError):
    code = "authority_exceeded"
    status_code = 409


class SettlementExceedsReserveError(ClaimsError):
    code = "settlement_exceeds_reserve"
    status_code = 409


class UnsupportedMediaTypeError(ClaimsError):
    code = "unsupported_media_type"
    status_code = 415
