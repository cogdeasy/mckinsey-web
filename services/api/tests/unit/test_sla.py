"""Unit tests for SLA clocks (FR-050 to FR-052)."""

from __future__ import annotations

from datetime import UTC, datetime

from claims_intake.domain.enums import Segment
from claims_intake.domain.sla import (
    add_business_days,
    add_business_hours,
    is_breached,
    targets_for,
)

FRIDAY_AFTERNOON = datetime(2026, 9, 11, 15, 0, tzinfo=UTC)
SATURDAY = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
MONDAY_MORNING = datetime(2026, 9, 14, 9, 30, tzinfo=UTC)


def test_business_hours_skip_the_weekend() -> None:
    assert add_business_hours(FRIDAY_AFTERNOON, 4) == datetime(2026, 9, 14, 11, 0, tzinfo=UTC)


def test_work_reported_at_the_weekend_starts_on_monday() -> None:
    assert add_business_hours(SATURDAY, 1) == datetime(2026, 9, 14, 10, 0, tzinfo=UTC)


def test_business_days_are_eight_business_hours() -> None:
    assert add_business_days(MONDAY_MORNING, 1) == datetime(2026, 9, 15, 9, 30, tzinfo=UTC)


def test_fr050_complex_claims_get_the_longer_decision_clock() -> None:
    standard = targets_for(MONDAY_MORNING, Segment.STANDARD)
    complex_claim = targets_for(MONDAY_MORNING, Segment.COMPLEX)
    assert complex_claim.decision_due_at > standard.decision_due_at
    assert standard.acknowledgement_due_at == datetime(2026, 9, 14, 13, 30, tzinfo=UTC)


def test_fr052_a_paused_clock_cannot_breach() -> None:
    due = datetime(2026, 9, 14, 9, 0, tzinfo=UTC)
    now = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    assert is_breached(due, now, awaiting_information=False) is True
    assert is_breached(due, now, awaiting_information=True) is False
    assert is_breached(None, now, awaiting_information=False) is False
