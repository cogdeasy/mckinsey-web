"""Shared response helpers: idempotent replay and documented error responses."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..schemas import ErrorResponse
from ..services import idempotency

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Malformed request"},
    401: {"model": ErrorResponse, "description": "Missing or invalid bearer token"},
    403: {"model": ErrorResponse, "description": "Insufficient role"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Conflicting state or idempotency key"},
    422: {"model": ErrorResponse, "description": "Validation failed"},
}


def replayed(
    session: Session, *, key: str | None, endpoint: str, payload: Any
) -> JSONResponse | None:
    stored = idempotency.find_replay(session, key=key, endpoint=endpoint, payload=payload)
    if stored is None:
        return None
    return JSONResponse(
        status_code=stored.status_code,
        content=stored.body,
        headers={"Idempotent-Replay": "true"},
    )


def persisted(
    session: Session,
    *,
    key: str | None,
    endpoint: str,
    payload: Any,
    status_code: int,
    model: BaseModel,
) -> JSONResponse:
    body = jsonable_encoder(model)
    idempotency.store(
        session,
        key=key,
        endpoint=endpoint,
        payload=payload,
        status_code=status_code,
        body=body,
    )
    return JSONResponse(status_code=status_code, content=body)
