"""Role-based financial authority limits (FR-041, FR-042)."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import Role

HANDLER_LIMIT_MINOR = 250_000
SENIOR_HANDLER_LIMIT_MINOR = 2_500_000
TECHNICAL_DESK_QUEUE = "technical-desk"

AUTHORITY_LIMITS: dict[Role, int] = {
    Role.CLAIMS_HANDLER: HANDLER_LIMIT_MINOR,
    Role.SENIOR_HANDLER: SENIOR_HANDLER_LIMIT_MINOR,
    Role.AUDITOR: 0,
}


@dataclass(frozen=True)
class AuthorityDecision:
    within_authority: bool
    limit_minor: int
    escalate_to_technical_desk: bool


def limit_for(roles: frozenset[Role]) -> int:
    return max((AUTHORITY_LIMITS.get(role, 0) for role in roles), default=0)


def evaluate(amount_minor: int, roles: frozenset[Role]) -> AuthorityDecision:
    """Decide whether an amount is within the actor's authority."""

    limit = limit_for(roles)
    return AuthorityDecision(
        within_authority=amount_minor <= limit,
        limit_minor=limit,
        escalate_to_technical_desk=amount_minor > SENIOR_HANDLER_LIMIT_MINOR,
    )
