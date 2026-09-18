"""Application factory for claims-intake-service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from . import __version__
from .api import routes_claims, routes_documents, routes_system
from .config import Settings, get_settings
from .db import get_engine
from .domain.rules import load_rule_set
from .errors import ClaimsError
from .observability.correlation import CORRELATION_HEADER, current_correlation_id
from .observability.logging import configure_logging, get_logger
from .observability.middleware import ObservabilityMiddleware
from .observability.tracing import configure_tracing, instrument_app
from .schemas import ErrorResponse
from .storage import S3DocumentStore

logger = get_logger("claims_intake.app")

DESCRIPTION = """
Claims intake and servicing for Meridian Assurance personal lines.

Implements the requirements in `docs/PRD.md`: first notification of loss, triage against a
versioned rule set, reserve authority, settlement, documents, SLA clocks and an immutable
audit trail.
""".strip()


def _error_response(error: ClaimsError) -> JSONResponse:
    body = ErrorResponse(
        code=error.code,
        message=error.message,
        details=error.details,
        correlation_id=current_correlation_id(),
    )
    return JSONResponse(status_code=error.status_code, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ClaimsError)
    async def handle_claims_error(_: Request, error: ClaimsError) -> JSONResponse:
        if error.status_code >= 500:
            logger.error("request.failed", extra={"error_code": error.code}, exc_info=error)
        return _error_response(error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            code="validation_error",
            message="The request failed validation",
            details={"errors": _serialise_validation(error)},
            correlation_id=current_correlation_id(),
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, error: Exception) -> JSONResponse:
        logger.error("request.unhandled_error", exc_info=error)
        body = ErrorResponse(
            code="internal_error",
            message="The request could not be completed",
            details={},
            correlation_id=current_correlation_id(),
        )
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def _serialise_validation(error: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {
            "location": [str(part) for part in item.get("loc", [])],
            "message": item.get("msg", ""),
            "type": item.get("type", ""),
        }
        for item in error.errors()
    ]


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Meridian Assurance Claims Intake API",
        version=__version__,
        description=DESCRIPTION,
        routes=app.routes,
        servers=[
            {"url": "https://claims.meridian-assurance.example", "description": "Production"},
            {"url": "http://localhost:8000", "description": "Local"},
        ],
    )
    schema["components"].setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "OIDC access token issued by the corporate identity provider.",
    }
    for path, operations in schema["paths"].items():
        if path in {"/healthz", "/readyz", "/metrics", "/"}:
            continue
        for operation in operations.values():
            operation.setdefault("security", [{"bearerAuth": []}])
    schema["info"]["contact"] = {
        "name": "Claims Platform",
        "email": "claims-platform@meridian-assurance.example",
    }
    app.openapi_schema = schema
    return schema


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level, resolved.service_name, resolved.environment)
    configure_tracing(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.rule_set = load_rule_set(resolved.rule_set_path)
        app.state.document_store = S3DocumentStore(resolved)
        logger.info(
            "service.started",
            extra={
                "rule_set_version": app.state.rule_set.version,
                "environment": resolved.environment,
            },
        )
        yield

    app = FastAPI(
        title="Meridian Assurance Claims Intake API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "https://claims-console.meridian-assurance.example",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_HEADER],
    )
    app.include_router(routes_claims.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_system.router)
    register_exception_handlers(app)
    app.openapi = lambda: custom_openapi(app)  # type: ignore[method-assign]

    instrument_app(app, get_engine(), resolved)
    return app


app = create_app()
