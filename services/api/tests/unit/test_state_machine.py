"""Unit tests for the claim lifecycle (FR-010 to FR-014)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from claims_intake.domain.enums import ClaimStatus, ReasonCode, Role
from claims_intake.domain.state_machine import (
    ALLOWED_TRANSITIONS,
    TransitionRequest,
    assert_transition_allowed,
    is_allowed,
    reachable_from,
)
from claims_intake.errors import InvalidTransitionError, ValidationError

HANDLER = frozenset({Role.CLAIMS_HANDLER})
SENIOR = frozenset({Role.SENIOR_HANDLER})


def test_fr010_every_status_is_in_the_transition_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(ClaimStatus)


def test_fr011_happy_path_is_walkable() -> None:
    path = [
        ClaimStatus.REGISTERED,
        ClaimStatus.TRIAGED,
        ClaimStatus.IN_ASSESSMENT,
        ClaimStatus.PENDING_APPROVAL,
        ClaimStatus.APPROVED,
        ClaimStatus.SETTLED,
        ClaimStatus.CLOSED,
    ]
    for source, target in pairwise(path):
        assert is_allowed(source, target), f"{source} to {target} should be permitted"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (ClaimStatus.REGISTERED, ClaimStatus.SETTLED),
        (ClaimStatus.SETTLED, ClaimStatus.IN_ASSESSMENT),
        (ClaimStatus.WITHDRAWN, ClaimStatus.APPROVED),
        (ClaimStatus.TRIAGED, ClaimStatus.APPROVED),
    ],
)
def test_fr011_illegal_transition_rejected(source: ClaimStatus, target: ClaimStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(TransitionRequest(source, target, SENIOR))


def test_fr013_reopening_a_closed_claim_requires_a_senior_handler() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition_allowed(
            TransitionRequest(ClaimStatus.CLOSED, ClaimStatus.IN_ASSESSMENT, HANDLER)
        )
    assert_transition_allowed(
        TransitionRequest(ClaimStatus.CLOSED, ClaimStatus.IN_ASSESSMENT, SENIOR)
    )


def test_fr014_rejection_requires_a_permitted_reason_code() -> None:
    with pytest.raises(ValidationError):
        assert_transition_allowed(
            TransitionRequest(ClaimStatus.TRIAGED, ClaimStatus.REJECTED, HANDLER)
        )
    with pytest.raises(ValidationError):
        assert_transition_allowed(
            TransitionRequest(
                ClaimStatus.TRIAGED,
                ClaimStatus.REJECTED,
                HANDLER,
                reason_code=ReasonCode.CUSTOMER_WITHDREW,
            )
        )
    assert_transition_allowed(
        TransitionRequest(
            ClaimStatus.TRIAGED, ClaimStatus.REJECTED, HANDLER, reason_code=ReasonCode.NO_COVER
        )
    )


def test_fr013_terminal_states_only_lead_to_closed() -> None:
    for status in (ClaimStatus.SETTLED, ClaimStatus.REJECTED, ClaimStatus.WITHDRAWN):
        assert reachable_from(status) == [ClaimStatus.CLOSED]
