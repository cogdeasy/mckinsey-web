"""Operational endpoints: health, readiness, metrics and the active rule set."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from .. import __version__
from ..observability.metrics import REGISTRY
from ..schemas import HealthResponse, ReadinessResponse, RuleSetView
from ..services import outbox
from ..views import rule_set_view
from .deps import DocumentStoreDep, PrincipalDep, RuleSetDep, SessionDep, SettingsDep

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness probe")
def healthz(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name, version=__version__)


@router.get("/readyz", response_model=ReadinessResponse, summary="Readiness probe")
def readyz(
    response: Response,
    session: SessionDep,
    store: DocumentStoreDep,
) -> ReadinessResponse:
    checks = {"database": False, "object_storage": False}
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = True
        outbox.refresh_gauges(session)
    except Exception:  # noqa: BLE001 - readiness reports, it does not raise
        checks["database"] = False
    checks["object_storage"] = store.healthy()

    ready = all(checks.values())
    if not ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if ready else "not_ready", checks=checks)


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@router.get(
    "/v1/rule-sets/current",
    response_model=RuleSetView,
    tags=["triage"],
    summary="Read the active triage rule set",
)
def current_rule_set(rule_set: RuleSetDep, principal: PrincipalDep) -> RuleSetView:
    return rule_set_view(rule_set)


@router.get("/", include_in_schema=False)
def root(request: Request) -> dict[str, str]:
    return {"service": "claims-intake-service", "docs": str(request.url_for("swagger_ui_html"))}
