"""Claim lifecycle as an explicit transition table (FR-010 to FR-014, ADR 0003).

Nothing outside this module may decide whether a status change is legal.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import InvalidTransitionError, ValidationError
from .enums import ClaimStatus, ReasonCode, Role

ALLOWED_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.REGISTERED: frozenset(
        {ClaimStatus.TRIAGED, ClaimStatus.REJECTED, ClaimStatus.WITHDRAWN}
    ),
    ClaimStatus.TRIAGED: frozenset(
        {ClaimStatus.IN_ASSESSMENT, ClaimStatus.REJECTED, ClaimStatus.WITHDRAWN}
    ),
    ClaimStatus.IN_ASSESSMENT: frozenset(
        {
            ClaimStatus.PENDING_APPROVAL,
            ClaimStatus.APPROVED,
            ClaimStatus.REJECTED,
            ClaimStatus.WITHDRAWN,
        }
    ),
    ClaimStatus.PENDING_APPROVAL: frozenset(
        {ClaimStatus.APPROVED, ClaimStatus.IN_ASSESSMENT, ClaimStatus.REJECTED}
    ),
    ClaimStatus.APPROVED: frozenset({ClaimStatus.SETTLED, ClaimStatus.IN_ASSESSMENT}),
    ClaimStatus.SETTLED: frozenset({ClaimStatus.CLOSED}),
    ClaimStatus.REJECTED: frozenset({ClaimStatus.CLOSED}),
    ClaimStatus.WITHDRAWN: frozenset({ClaimStatus.CLOSED}),
    ClaimStatus.CLOSED: frozenset({ClaimStatus.IN_ASSESSMENT}),
}

REASON_REQUIRED: frozenset[ClaimStatus] = frozenset({ClaimStatus.REJECTED, ClaimStatus.WITHDRAWN})

VALID_REASONS: dict[ClaimStatus, frozenset[ReasonCode]] = {
    ClaimStatus.REJECTED: frozenset(
        {ReasonCode.NO_COVER, ReasonCode.POLICY_LAPSED, ReasonCode.FRAUD_CONFIRMED}
    ),
    ClaimStatus.WITHDRAWN: frozenset(
        {ReasonCode.CUSTOMER_WITHDREW, ReasonCode.DUPLICATE_NOTIFICATION}
    ),
}

# Reopening a closed claim is a senior-handler action only (FR-013).
RESTRICTED_TRANSITIONS: dict[tuple[ClaimStatus, ClaimStatus], frozenset[Role]] = {
    (ClaimStatus.CLOSED, ClaimStatus.IN_ASSESSMENT): frozenset({Role.SENIOR_HANDLER}),
    (ClaimStatus.PENDING_APPROVAL, ClaimStatus.APPROVED): frozenset({Role.SENIOR_HANDLER}),
    (ClaimStatus.APPROVED, ClaimStatus.SETTLED): frozenset({Role.SENIOR_HANDLER}),
}


@dataclass(frozen=True)
class TransitionRequest:
    source: ClaimStatus
    target: ClaimStatus
    roles: frozenset[Role]
    reason_code: ReasonCode | None = None


def is_allowed(source: ClaimStatus, target: ClaimStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, frozenset())


def assert_transition_allowed(request: TransitionRequest) -> None:
    """Raise unless the transition is legal for the claim and the actor."""

    if not is_allowed(request.source, request.target):
        raise InvalidTransitionError(
            f"A claim cannot move from {request.source} to {request.target}",
            {"from": request.source.value, "to": request.target.value},
        )

    required = RESTRICTED_TRANSITIONS.get((request.source, request.target))
    if required is not None and not (request.roles & required):
        raise InvalidTransitionError(
            f"Moving from {request.source} to {request.target} requires one of "
            + ", ".join(sorted(role.value for role in required)),
            {"required_roles": sorted(role.value for role in required)},
        )

    if request.target in REASON_REQUIRED:
        if request.reason_code is None:
            raise ValidationError(
                f"A reason code is required to move a claim to {request.target}",
                {"to": request.target.value},
            )
        permitted = VALID_REASONS[request.target]
        if request.reason_code not in permitted:
            raise ValidationError(
                f"Reason code {request.reason_code} is not valid for {request.target}",
                {"permitted": sorted(code.value for code in permitted)},
            )


def reachable_from(source: ClaimStatus) -> list[ClaimStatus]:
    return sorted(ALLOWED_TRANSITIONS.get(source, frozenset()), key=lambda status: status.value)
