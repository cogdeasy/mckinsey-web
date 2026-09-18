"""Bearer token verification and role extraction (FR-080 to FR-083)."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from jwt import PyJWTError

from .config import Settings
from .domain.enums import Role
from .errors import ForbiddenError, UnauthorizedError

LOCAL_PRINCIPAL_SUBJECT = "local-development"


@dataclass(frozen=True)
class Principal:
    subject: str
    display_name: str
    roles: frozenset[Role]

    @property
    def primary_role(self) -> Role:
        for role in (Role.SENIOR_HANDLER, Role.CLAIMS_HANDLER, Role.AUDITOR):
            if role in self.roles:
                return role
        raise ForbiddenError("The token carries no recognised claims role")

    def require_write(self) -> None:
        """The auditor role is read-only on every write path (FR-082)."""

        if not self.roles & {Role.CLAIMS_HANDLER, Role.SENIOR_HANDLER}:
            raise ForbiddenError("This action requires a claims handler role")

    def require_senior(self) -> None:
        if Role.SENIOR_HANDLER not in self.roles:
            raise ForbiddenError("This action requires the senior handler role")


def decode_principal(token: str, settings: Settings) -> Principal:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except PyJWTError as exc:
        raise UnauthorizedError("The bearer token could not be verified") from exc

    raw_roles = payload.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles = frozenset(Role(role) for role in raw_roles if role in set(Role))
    if not roles:
        raise ForbiddenError("The token carries no recognised claims role")

    subject = str(payload["sub"])
    return Principal(
        subject=subject,
        display_name=str(payload.get("name") or subject),
        roles=roles,
    )


def local_principal() -> Principal:
    """Principal used when authentication is disabled for local development only."""

    return Principal(
        subject=LOCAL_PRINCIPAL_SUBJECT,
        display_name="Local developer",
        roles=frozenset({Role.CLAIMS_HANDLER, Role.SENIOR_HANDLER, Role.AUDITOR}),
    )
