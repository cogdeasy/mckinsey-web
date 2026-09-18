"""Correlation, access logging and metrics middleware."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .correlation import CORRELATION_HEADER, correlation_id_var, new_correlation_id
from .logging import get_logger
from .metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = get_logger("claims_intake.access")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else request.url.path


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID, emit an access log line and record metrics."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or new_correlation_id()
        token = correlation_id_var.set(correlation_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration = time.perf_counter() - started
            correlation_id_var.reset(token)

        path = _route_template(request)
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        response.headers[CORRELATION_HEADER] = correlation_id
        if path not in {"/metrics", "/healthz", "/readyz"}:
            logger.info(
                "request.completed",
                extra={
                    "http_method": request.method,
                    "http_path": path,
                    "http_status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "correlation_id": correlation_id,
                },
            )
        return response
