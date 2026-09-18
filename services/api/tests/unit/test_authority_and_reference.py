"""Unit tests for authority limits (FR-041) and claim references (FR-003)."""

from __future__ import annotations

import pytest

from claims_intake.domain.authority import (
    HANDLER_LIMIT_MINOR,
    SENIOR_HANDLER_LIMIT_MINOR,
    evaluate,
)
from claims_intake.domain.enums import Role
from claims_intake.domain.reference import format_reference, is_valid_reference

HANDLER = frozenset({Role.CLAIMS_HANDLER})
SENIOR = frozenset({Role.SENIOR_HANDLER})
AUDITOR = frozenset({Role.AUDITOR})


def test_fr041_handler_limit() -> None:
    assert evaluate(HANDLER_LIMIT_MINOR, HANDLER).within_authority is True
    assert evaluate(HANDLER_LIMIT_MINOR + 1, HANDLER).within_authority is False


def test_fr041_senior_limit_and_escalation() -> None:
    decision = evaluate(SENIOR_HANDLER_LIMIT_MINOR + 1, SENIOR)
    assert decision.within_authority is False
    assert decision.escalate_to_technical_desk is True


def test_fr082_auditor_has_no_financial_authority() -> None:
    assert evaluate(1, AUDITOR).within_authority is False


def test_fr003_reference_format() -> None:
    assert format_reference(2026, 123) == "MER-2026-000123"
    assert is_valid_reference("MER-2026-000123") is True
    assert is_valid_reference("CLM-2026-000123") is False


def test_fr003_sequence_bounds_are_enforced() -> None:
    with pytest.raises(ValueError, match="sequence"):
        format_reference(2026, 0)
