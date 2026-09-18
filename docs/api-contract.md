# Claims Intake API contract

Base path `/v1`. The machine-readable contract is `services/api/openapi.json`, generated from
the implementation and asserted in CI (FR-092). This document explains the intent, the
lifecycle and the error model; where the two disagree, the generated document is authoritative
and the mismatch is a bug.

## Authentication and roles

All `/v1` endpoints require `Authorization: Bearer <jwt>` (FR-080). Tokens are verified for
signature, `iss`, `aud` and `exp` (FR-081). The `roles` claim carries one or more of:

| Role | Read claims | Write claims | Approve | Settle |
| --- | --- | --- | --- | --- |
| `claims_handler` | yes | yes | no | no |
| `senior_handler` | yes | yes | yes | yes |
| `auditor` | yes (all claims) | no | no | no |

Unauthenticated requests return `401 unauthorized`; authenticated but insufficient requests
return `403 forbidden` (FR-083).

## Conventions

- **Correlation** — supply `X-Correlation-Id`; it is echoed on the response and attached to
  logs, traces, audit events and outbox entries (FR-093, FR-072).
- **Idempotency** — `POST` endpoints accept `Idempotency-Key`. A replay with the same body
  returns the stored response; a replay with a different body returns `409
  idempotency_key_reuse` (FR-004, FR-005).
- **Pagination** — list endpoints take `limit` (default 25, max 100) and `cursor`, and return
  `{ "items": [...], "next_cursor": "..." | null }` (FR-090).
- **Money** — integer minor units plus an ISO 4217 `currency`. Never a float.
- **Errors** — every non-2xx response is

  ```json
  {
    "code": "invalid_transition",
    "message": "Claim MER-2026-000123 cannot move from SETTLED to IN_ASSESSMENT",
    "details": {"from": "SETTLED", "to": "IN_ASSESSMENT"},
    "correlation_id": "0f8c1f1e-2f2d-4a0e-9a2b-2a9d9c6f1c4a"
  }
  ```

  Codes: `validation_error` (422), `unauthorized` (401), `forbidden` (403), `not_found` (404),
  `invalid_transition` (409), `idempotency_key_reuse` (409), `authority_exceeded` (409),
  `settlement_exceeds_reserve` (409), `unsupported_media_type` (415), `internal_error` (500).

## Lifecycle (FR-010, FR-011)

```
REGISTERED ──▶ TRIAGED ──▶ IN_ASSESSMENT ──▶ PENDING_APPROVAL ──▶ APPROVED ──▶ SETTLED ──▶ CLOSED
     │             │              │                  │                │                      ▲
     │             │              │                  └──▶ IN_ASSESSMENT (declined)           │
     │             │              └──▶ REJECTED ─────────────────────────────────────────────┤
     ├─────────────┴──▶ WITHDRAWN ───────────────────────────────────────────────────────────┘
                                                            CLOSED ──▶ IN_ASSESSMENT (reopen, senior handler only)
```

Terminal for handler actions: `SETTLED`, `REJECTED`, `WITHDRAWN`, `CLOSED` (FR-013). `REJECTED`
and `WITHDRAWN` require a reason code (FR-014).

## Endpoints

| Method | Path | Purpose | Requirements |
| --- | --- | --- | --- |
| `POST` | `/v1/claims` | Register an FNOL, allocate a reference, run triage | FR-001–FR-006, FR-020 |
| `GET` | `/v1/claims` | Queue listing with filters `status`, `segment`, `queue`, `breached`, `policy_reference` | FR-090, FR-100 |
| `GET` | `/v1/claims/{claim_reference}` | Claim detail including current triage decision, reserves, SLA | FR-101 |
| `GET` | `/v1/claims/{claim_reference}/timeline` | Ordered lifecycle, reserve, document and payment events | FR-012, FR-101 |
| `POST` | `/v1/claims/{claim_reference}/transitions` | Apply a lifecycle transition | FR-011–FR-014 |
| `POST` | `/v1/claims/{claim_reference}/triage` | Re-run triage, creating a new decision | FR-024 |
| `POST` | `/v1/claims/{claim_reference}/reserves` | Propose or set a reserve | FR-040–FR-042 |
| `GET` | `/v1/claims/{claim_reference}/reserves` | Append-only reserve history | FR-040 |
| `POST` | `/v1/claims/{claim_reference}/approvals` | Approve or decline a pending amount (senior handler) | FR-043 |
| `POST` | `/v1/claims/{claim_reference}/settlements` | Raise a payment instruction (senior handler) | FR-044, FR-045, FR-070 |
| `POST` | `/v1/claims/{claim_reference}/documents` | Request a pre-signed upload URL | FR-030, FR-031 |
| `POST` | `/v1/claims/{claim_reference}/documents/{document_id}/confirm` | Confirm an upload and attach it | FR-032 |
| `GET` | `/v1/claims/{claim_reference}/documents` | List documents | FR-032 |
| `GET` | `/v1/claims/{claim_reference}/documents/{document_id}/download-url` | Short-lived download URL | FR-033 |
| `GET` | `/v1/claims/{claim_reference}/audit-events` | Audit trail for a claim | FR-060–FR-062 |
| `GET` | `/v1/rule-sets/current` | Active triage rule set and version | FR-021 |
| `GET` | `/healthz` | Liveness, no dependencies | NFR-002 |
| `GET` | `/readyz` | Readiness, checks database and object storage | NFR-002 |
| `GET` | `/metrics` | Prometheus exposition | NFR-005 |

### `POST /v1/claims`

```json
{
  "policy_reference": "POL-88213371",
  "product": "MOTOR",
  "loss_datetime": "2026-09-14T07:40:00Z",
  "peril": "COLLISION",
  "loss_description": "Rear-ended at a junction on the A34, third party admitted liability.",
  "estimated_exposure_minor": 480000,
  "currency": "GBP",
  "incident_location": {"line1": "A34 northbound", "city": "Oxford", "postcode": "OX2 8JD", "country": "GB"},
  "policyholder": {"full_name": "R. Whitfield", "email": "r.whitfield@example.com", "phone": "+441865000000"},
  "fraud_indicator": false,
  "channel": "CONTACT_CENTRE"
}
```

Response `201`:

```json
{
  "claim_reference": "MER-2026-000123",
  "status": "TRIAGED",
  "duplicate_suspected": false,
  "triage": {"segment": "STANDARD", "priority": 3, "queue": "motor-standard", "rule_id": "motor-standard-exposure", "rule_set_version": "1.3.0"},
  "sla": {"acknowledgement_due_at": "2026-09-14T11:40:00Z", "decision_due_at": "2026-10-05T07:40:00Z", "breached": false},
  "created_at": "2026-09-14T07:41:02Z"
}
```

### Triage facts

The closed fact schema available to rules (ADR 0004):

| Fact | Type | Source |
| --- | --- | --- |
| `product` | enum `MOTOR`, `HOME`, `TRAVEL` | FNOL |
| `peril` | enum, see OpenAPI | FNOL |
| `estimated_exposure_minor` | integer | FNOL |
| `fraud_indicator` | boolean | FNOL / fraud service |
| `duplicate_suspected` | boolean | derived (FR-006) |
| `channel` | enum `CONTACT_CENTRE`, `PORTAL`, `BROKER`, `MOBILE` | FNOL |
| `days_since_loss` | integer | derived |
| `policyholder_country` | ISO 3166-1 alpha-2 | FNOL |

A rule referencing any other fact fails validation at load time and the service refuses to
start.

## Versioning

The path carries the major version. Additive changes (new optional fields, new enum members on
response-only enums) ship without a version bump; consumers must ignore unknown fields.
Breaking changes require `/v2` and a deprecation window of two quarters.
