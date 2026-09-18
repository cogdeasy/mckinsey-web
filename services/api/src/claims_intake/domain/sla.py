"""SLA clocks for acknowledgement, first contact and decision (FR-050 to FR-052)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .enums import Segment

BUSINESS_DAY_START = time(9, 0)
BUSINESS_DAY_END = time(17, 0)
BUSINESS_HOURS_PER_DAY = 8

ACKNOWLEDGEMENT_BUSINESS_HOURS = 4
FIRST_CONTACT_BUSINESS_DAYS = 1
DECISION_BUSINESS_DAYS = 15
DECISION_BUSINESS_DAYS_COMPLEX = 30


@dataclass(frozen=True)
class SlaTargets:
    acknowledgement_due_at: datetime
    first_contact_due_at: datetime
    decision_due_at: datetime


def _is_business_day(moment: datetime) -> bool:
    return moment.weekday() < 5


def _start_of_business(moment: datetime) -> datetime:
    return moment.replace(hour=BUSINESS_DAY_START.hour, minute=0, second=0, microsecond=0)


def _end_of_business(moment: datetime) -> datetime:
    return moment.replace(hour=BUSINESS_DAY_END.hour, minute=0, second=0, microsecond=0)


def _advance_to_business_time(moment: datetime) -> datetime:
    cursor = moment
    while True:
        if not _is_business_day(cursor):
            cursor = _start_of_business(cursor + timedelta(days=1))
            continue
        cursor = max(cursor, _start_of_business(cursor))
        if cursor >= _end_of_business(cursor):
            cursor = _start_of_business(cursor + timedelta(days=1))
            continue
        return cursor


def add_business_hours(start: datetime, hours: int) -> datetime:
    """Add working hours, skipping nights and weekends."""

    if hours < 0:
        raise ValueError("hours must not be negative")
    cursor = _advance_to_business_time(start)
    remaining = timedelta(hours=hours)
    while remaining > timedelta(0):
        available = _end_of_business(cursor) - cursor
        if available >= remaining:
            return cursor + remaining
        remaining -= available
        cursor = _advance_to_business_time(_end_of_business(cursor))
    return cursor


def add_business_days(start: datetime, days: int) -> datetime:
    return add_business_hours(start, days * BUSINESS_HOURS_PER_DAY)


def targets_for(reported_at: datetime, segment: Segment) -> SlaTargets:
    decision_days = (
        DECISION_BUSINESS_DAYS_COMPLEX if segment is Segment.COMPLEX else DECISION_BUSINESS_DAYS
    )
    return SlaTargets(
        acknowledgement_due_at=add_business_hours(reported_at, ACKNOWLEDGEMENT_BUSINESS_HOURS),
        first_contact_due_at=add_business_days(reported_at, FIRST_CONTACT_BUSINESS_DAYS),
        decision_due_at=add_business_days(reported_at, decision_days),
    )


def is_breached(due_at: datetime | None, now: datetime, awaiting_information: bool) -> bool:
    """A paused clock cannot breach (FR-052)."""

    if due_at is None or awaiting_information:
        return False
    return now > due_at
