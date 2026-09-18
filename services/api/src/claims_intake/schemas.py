"""Request and response models. These generate the OpenAPI document (FR-092)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from .domain.enums import (
    Channel,
    ClaimStatus,
    DocumentKind,
    DocumentState,
    PaymentState,
    Peril,
    Product,
    ReasonCode,
    ReserveCategory,
    ReserveState,
    Role,
    Segment,
)

ItemT = TypeVar("ItemT")

Currency = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
CountryCode = Annotated[str, StringConstraints(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")]
PolicyReference = Annotated[
    str, StringConstraints(min_length=6, max_length=32, pattern=r"^[A-Z0-9-]+$")
]
AmountMinor = Annotated[int, Field(ge=0, le=10_000_000_000)]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorResponse(ApiModel):
    """The single error envelope used by every endpoint (FR-091)."""

    code: str = Field(examples=["invalid_transition"])
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class Page(ApiModel, Generic[ItemT]):
    items: list[ItemT]
    next_cursor: str | None = None


class Address(ApiModel):
    line1: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=80)
    postcode: str | None = Field(default=None, max_length=16)
    country: CountryCode = "GB"


class Policyholder(ApiModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)


class ClaimCreate(ApiModel):
    """FNOL submission (FR-001)."""

    policy_reference: PolicyReference
    product: Product
    peril: Peril
    channel: Channel = Channel.CONTACT_CENTRE
    loss_datetime: datetime
    loss_description: str = Field(min_length=10, max_length=4000)
    estimated_exposure_minor: AmountMinor
    currency: Currency = "GBP"
    policyholder: Policyholder
    incident_location: Address | None = None
    fraud_indicator: bool = False


class TriageView(ApiModel):
    segment: Segment
    priority: int = Field(ge=1, le=5)
    queue: str
    rule_id: str
    rule_set_version: str
    decided_at: datetime


class SlaView(ApiModel):
    acknowledgement_due_at: datetime | None
    first_contact_due_at: datetime | None
    decision_due_at: datetime | None
    awaiting_information: bool
    breached: bool


class ReserveView(ApiModel):
    id: uuid.UUID
    category: ReserveCategory
    amount_minor: int
    currency: Currency
    state: ReserveState
    note: str | None
    actor_id: str
    decided_by: str | None
    created_at: datetime


class PaymentView(ApiModel):
    id: uuid.UUID
    amount_minor: int
    currency: Currency
    payee_name: str
    payee_reference: str
    state: PaymentState
    created_at: datetime


class DocumentView(ApiModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    kind: DocumentKind
    state: DocumentState
    uploaded_by: str
    created_at: datetime
    confirmed_at: datetime | None


class ClaimSummary(ApiModel):
    """Queue row (FR-100)."""

    claim_reference: str
    policy_reference: str
    product: Product
    peril: Peril
    status: ClaimStatus
    segment: Segment | None
    priority: int | None
    queue: str | None
    policyholder_name: str
    estimated_exposure_minor: int
    currency: Currency
    duplicate_suspected: bool
    reported_at: datetime
    sla: SlaView


class ClaimDetail(ClaimSummary):
    """Claim detail (FR-101)."""

    id: uuid.UUID
    channel: Channel
    loss_datetime: datetime
    loss_description: str
    fraud_indicator: bool
    incident_location: Address | None
    policyholder: Policyholder
    triage: TriageView | None
    reserves: list[ReserveView]
    documents: list[DocumentView]
    payments: list[PaymentView]
    indemnity_reserve_minor: int
    settled_minor: int
    pending_amount_minor: int | None
    created_at: datetime
    updated_at: datetime


class TransitionCreate(ApiModel):
    target_status: ClaimStatus
    reason_code: ReasonCode | None = None
    note: str | None = Field(default=None, max_length=2000)


class TransitionView(ApiModel):
    id: uuid.UUID
    from_status: ClaimStatus | None
    to_status: ClaimStatus
    reason_code: ReasonCode | None
    note: str | None
    actor_id: str
    actor_role: Role
    correlation_id: str
    created_at: datetime


class ReserveCreate(ApiModel):
    category: ReserveCategory = ReserveCategory.INDEMNITY
    amount_minor: AmountMinor
    currency: Currency = "GBP"
    note: str | None = Field(default=None, max_length=2000)


class ReserveResult(ApiModel):
    reserve: ReserveView
    claim_status: ClaimStatus
    requires_approval: bool
    authority_limit_minor: int


class ApprovalCreate(ApiModel):
    decision: Literal["APPROVE", "DECLINE"]
    note: str = Field(min_length=3, max_length=2000)


class SettlementCreate(ApiModel):
    amount_minor: AmountMinor
    currency: Currency = "GBP"
    payee_name: str = Field(min_length=2, max_length=160)
    payee_reference: str = Field(min_length=4, max_length=64)
    note: str | None = Field(default=None, max_length=2000)


class DocumentCreate(ApiModel):
    filename: str = Field(min_length=3, max_length=255)
    content_type: str = Field(min_length=3, max_length=80)
    size_bytes: int = Field(gt=0)
    kind: DocumentKind = DocumentKind.OTHER


class DocumentUploadTicket(ApiModel):
    document: DocumentView
    upload_url: str
    storage_key: str
    expires_in_seconds: int


class DocumentConfirm(ApiModel):
    checksum_sha256: Annotated[
        str, StringConstraints(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    ]


class DownloadTicket(ApiModel):
    download_url: str
    expires_in_seconds: int


class TimelineEntry(ApiModel):
    """A projection over transitions, reserves, documents and payments (FR-101)."""

    occurred_at: datetime
    kind: Literal["TRANSITION", "TRIAGE", "RESERVE", "DOCUMENT", "PAYMENT"]
    summary: str
    actor_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditEventView(ApiModel):
    id: uuid.UUID
    claim_reference: str | None
    event_type: str
    actor_id: str
    actor_role: Role
    correlation_id: str
    payload: dict[str, Any]
    payload_digest: str
    created_at: datetime


class RuleOutcomeView(ApiModel):
    segment: Segment
    priority: int
    queue: str


class RuleView(ApiModel):
    id: str
    description: str
    when: dict[str, dict[str, Any]]
    then: RuleOutcomeView


class RuleSetView(ApiModel):
    version: str
    rules: list[RuleView]
    default: RuleOutcomeView


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str


class ReadinessResponse(ApiModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]
