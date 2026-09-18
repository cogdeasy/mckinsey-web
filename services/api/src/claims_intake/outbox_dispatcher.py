"""Standalone outbox dispatcher process (ADR 0005).

Runs beside the API so that broker latency never affects request latency.
"""

from __future__ import annotations

import signal
import time
from types import FrameType

from prometheus_client import start_http_server

from .config import get_settings
from .db import session_scope
from .models import OutboxEntry
from .observability.logging import configure_logging, get_logger
from .observability.metrics import REGISTRY
from .services import outbox

logger = get_logger("claims_intake.dispatcher")

_running = True


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _running
    logger.info("dispatcher.stopping", extra={"signal": signum})
    _running = False


def log_publisher(entry: OutboxEntry) -> None:
    """Default publisher.

    The payments hub and communications broker adapters are injected in the deployed
    environments; locally the entry is logged so the flow is observable end to end.
    """

    logger.info(
        "outbox.published",
        extra={
            "topic": entry.topic,
            "outbox_id": str(entry.id),
            "correlation_id": entry.correlation_id,
        },
    )


def run() -> None:
    settings = get_settings()
    configure_logging(
        settings.log_level, f"{settings.service_name}-dispatcher", settings.environment
    )
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    start_http_server(9101, registry=REGISTRY)
    logger.info("dispatcher.started", extra={"batch_size": settings.outbox_batch_size})

    while _running:
        with session_scope() as session:
            published = outbox.dispatch_batch(
                session,
                log_publisher,
                batch_size=settings.outbox_batch_size,
                max_attempts=settings.outbox_max_attempts,
            )
        if published == 0:
            time.sleep(settings.outbox_poll_seconds)


if __name__ == "__main__":  # pragma: no cover - process entry point
    run()
