"""Unit tests for idempotency digests (FR-004, FR-005)."""

from __future__ import annotations

from claims_intake.services.idempotency import request_digest


def test_digest_is_stable_across_key_order() -> None:
    assert request_digest({"a": 1, "b": [1, 2]}) == request_digest({"b": [1, 2], "a": 1})


def test_digest_changes_when_the_body_changes() -> None:
    assert request_digest({"amount_minor": 100}) != request_digest({"amount_minor": 101})
