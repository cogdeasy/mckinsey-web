"""Prometheus metrics (NFR-005)."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry(auto_describe=True)

REQUEST_COUNT = Counter(
    "claims_http_requests_total",
    "HTTP requests handled by the claims API.",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "claims_http_request_duration_seconds",
    "Request latency by route.",
    labelnames=("method", "path"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.3, 2.1, 5.0),
    registry=REGISTRY,
)

TRIAGE_DECISIONS = Counter(
    "claims_triage_decisions_total",
    "Triage decisions by segment and rule set version.",
    labelnames=("segment", "rule_set_version"),
    registry=REGISTRY,
)

CLAIMS_REGISTERED = Counter(
    "claims_registered_total",
    "Claims registered by product and channel.",
    labelnames=("product", "channel"),
    registry=REGISTRY,
)

OUTBOX_DEPTH = Gauge(
    "claims_outbox_pending",
    "Outbox entries awaiting dispatch.",
    registry=REGISTRY,
)

OUTBOX_DEAD_LETTERS = Gauge(
    "claims_outbox_dead_letters",
    "Outbox entries that exhausted their retries.",
    registry=REGISTRY,
)

OUTBOX_PUBLISHED = Counter(
    "claims_outbox_published_total",
    "Outbox entries published by topic.",
    labelnames=("topic",),
    registry=REGISTRY,
)
