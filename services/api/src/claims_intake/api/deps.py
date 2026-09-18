"""FastAPI dependencies: settings, database session, principal, rule set, storage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_session_factory
from ..domain.rules import RuleSet
from ..errors import UnauthorizedError
from ..observability.correlation import current_correlation_id
from ..security import Principal, decode_principal, local_principal
from ..storage import DocumentStore


def settings_dependency() -> Settings:
    return get_settings()


def session_dependency() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def principal_dependency(
    settings: Annotated[Settings, Depends(settings_dependency)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if settings.auth_disabled:
        return local_principal()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("A bearer token is required")
    return decode_principal(authorization.split(" ", 1)[1].strip(), settings)


def correlation_dependency() -> str:
    return current_correlation_id()


def idempotency_key_dependency(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    return idempotency_key


def rule_set_dependency(request: Request) -> RuleSet:
    rule_set = getattr(request.app.state, "rule_set", None)
    if rule_set is None:  # pragma: no cover - the app always loads a rule set at startup
        raise RuntimeError("No triage rule set is loaded")
    return cast(RuleSet, rule_set)


def document_store_dependency(request: Request) -> DocumentStore:
    store = getattr(request.app.state, "document_store", None)
    if store is None:  # pragma: no cover - configured at startup
        raise RuntimeError("No document store is configured")
    return cast(DocumentStore, store)


SettingsDep = Annotated[Settings, Depends(settings_dependency)]
SessionDep = Annotated[Session, Depends(session_dependency)]
PrincipalDep = Annotated[Principal, Depends(principal_dependency)]
CorrelationDep = Annotated[str, Depends(correlation_dependency)]
IdempotencyDep = Annotated[str | None, Depends(idempotency_key_dependency)]
RuleSetDep = Annotated[RuleSet, Depends(rule_set_dependency)]
DocumentStoreDep = Annotated[DocumentStore, Depends(document_store_dependency)]
