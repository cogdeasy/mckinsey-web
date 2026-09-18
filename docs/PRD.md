# Product Requirements Document: Claims Intake & Servicing Platform

| Field | Value |
| --- | --- |
| Product | `claims-intake-service` (API) + Claims Ops Console (web) |
| Business unit | Meridian Assurance — Personal Lines Claims |
| Status | APPROVED |
| Owner | Claims Platform (claims-platform@meridian-assurance.example) |
| Version | 1.2 |
| Last updated | 2026-09-18 |

## 1. Executive summary

Meridian Assurance replaces the first-notification-of-loss (FNOL) and early-life claim
servicing capability currently delivered by the mainframe-backed `CLMS7` green screens with a
service-oriented platform. This document is the contract between the claims operation and the
Claims Platform engineering team: it defines the personas, journeys, functional requirements
(FR-xxx) and non-functional requirements (NFR-xxx) that the implementation must satisfy.

## 2. Background and problem statement

Personal Lines takes roughly 4,200 new claims per week across motor, home and travel. Today:

- FNOL is captured in a call-centre script and rekeyed into `CLMS7` by a handler. Median time
  to a claim reference is 11 minutes; 6% of claims are duplicated by repeat calls.
- Triage and routing are governed by a spreadsheet of rules maintained by the Claims Technical
  team. Changes take a release cycle to reach production, and there is no audit of which rule
  version decided a given claim.
- Reserve changes and settlement payments are recorded in two systems with a nightly
  reconciliation; finance raises on average 40 breaks per month.
- Regulatory evidence (who saw what, who changed what, when) is assembled by hand from
  mainframe journals when the FCA or an ombudsman case requires it.

The platform must remove the rekeying, make the rules a versioned and auditable asset, and
produce a single, queryable claim timeline.

## 3. Personas

| ID | Persona | Description | Primary needs |
| --- | --- | --- | --- |
| P1 | **Claims handler** (Dana) | Front-line handler, 60–80 claims in flight | Fast intake, a prioritised queue, one screen per claim |
| P2 | **Senior claims handler** (Omar) | Approves reserves and payments above handler limits | Approval queue, exposure visibility, override with reason |
| P3 | **Claims auditor** (Priya) | Second line / compliance | Immutable timeline, rule-version attribution, export |
| P4 | **Policyholder** (indirect) | Customer reporting a loss | Acknowledgement, SLA-bound updates |
| P5 | **Platform engineer** | Runs the service | Health endpoints, traces, metrics, replayable outbox |

Policyholders do not interact with this system directly in the current scope; the customer
portal and the contact-centre desktop both call the API.

## 4. User journeys

### J1 — Notify a loss (P1, P4)
The handler captures policy number, loss date, peril, description and contact details. The
service validates the policy reference, checks for a duplicate notification, allocates a claim
reference (`MER-<year>-<sequence>`), runs triage, sets an initial reserve band and places the
claim in a queue. The handler reads back the reference to the customer.

### J2 — Work the queue (P1)
The handler opens the queue filtered by their skill and segment, sorted by SLA risk. Opening a
claim shows the timeline, documents, reserve history and the triage decision with the rule set
version that produced it.

### J3 — Collect evidence (P1, P4)
Documents (photos, repair estimates, police reports) are uploaded against the claim to object
storage via pre-signed URLs, then scanned and attached to the timeline.

### J4 — Reserve and approve (P1, P2)
The handler proposes a reserve. If the amount exceeds their authority limit the claim enters
`PENDING_APPROVAL` and appears in the senior handler's approval queue with the delta and the
reason.

### J5 — Settle (P2)
An approved settlement creates a payment instruction. The instruction is written to the
notification/payment outbox for the downstream payments hub; the claim moves to `SETTLED` once
the instruction is acknowledged.

### J6 — Audit a claim (P3)
The auditor searches by claim reference or policy number and reads the full timeline: every
state transition, actor, rule version, reserve change and document event, with no ability to
mutate anything.

## 5. Functional requirements

### 5.1 Intake (FNOL)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-001 | The API accepts an FNOL submission containing policy reference, policyholder contact, loss datetime, peril, loss description and optional incident location. | Must |
| FR-002 | Loss datetime must not be in the future and must be within the policy's cover window; violations return a structured `validation_error`. | Must |
| FR-003 | Every accepted FNOL is allocated a human-readable claim reference `MER-<YYYY>-<6-digit sequence>`, unique for the lifetime of the system. | Must |
| FR-004 | Write endpoints accept an `Idempotency-Key` header. A repeated key with an identical request body returns the original response and creates no new state. | Must |
| FR-005 | A repeated `Idempotency-Key` with a different request body returns `409 idempotency_key_reuse`. | Must |
| FR-006 | Duplicate detection flags an FNOL when the same policy reference and loss date are notified within 72 hours; the claim is created with `duplicate_suspected = true` rather than rejected. | Should |

### 5.2 Lifecycle and state machine

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-010 | A claim occupies exactly one of: `REGISTERED`, `TRIAGED`, `IN_ASSESSMENT`, `PENDING_APPROVAL`, `APPROVED`, `SETTLED`, `REJECTED`, `WITHDRAWN`, `CLOSED`. | Must |
| FR-011 | Transitions are permitted only along the documented edges (see `docs/api-contract.md`); an illegal transition returns `409 invalid_transition` and changes nothing. | Must |
| FR-012 | Every transition records actor, timestamp, source state, target state and a reason code, and is exposed on the claim timeline. | Must |
| FR-013 | `SETTLED`, `REJECTED`, `WITHDRAWN` and `CLOSED` are terminal for handler actions; only an auditor-visible reopen by a senior handler may leave `CLOSED`, moving the claim to `IN_ASSESSMENT`. | Must |
| FR-014 | Rejection and withdrawal require a reason code from the published enumeration. | Must |

### 5.3 Triage and routing

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-020 | Triage evaluates a versioned, declarative rule set against the claim and produces a segment (`FAST_TRACK`, `STANDARD`, `COMPLEX`, `SPECIAL_INVESTIGATION`), a priority (1–5) and a target queue. | Must |
| FR-021 | The rule set version that produced a decision is persisted with the decision and surfaced in the API and console. | Must |
| FR-022 | Rules are evaluated in declared order; the first matching rule wins, and an explicit default rule guarantees a decision. | Must |
| FR-023 | Claims with an estimated exposure above the complex threshold, or a fraud indicator, must never be routed to `FAST_TRACK`. | Must |
| FR-024 | Re-running triage on a claim creates a new decision record rather than overwriting the previous one. | Should |

### 5.4 Documents

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-030 | A handler may request a pre-signed upload URL for a claim document, supplying filename, content type and size. | Must |
| FR-031 | Content types are restricted to PDF, JPEG, PNG and HEIC; size is capped at 25 MB. | Must |
| FR-032 | Document metadata (kind, uploader, checksum, storage key) is recorded and appears on the timeline once the upload is confirmed. | Must |
| FR-033 | Documents are read back through a short-lived pre-signed download URL; the object store is never public. | Must |

### 5.5 Reserves, authority and settlement

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-040 | A reserve is an amount in minor units with a currency and a category (`INDEMNITY`, `EXPENSE`). Reserve history is append-only. | Must |
| FR-041 | Authority limits are role-based: handler 250,000 minor units, senior handler 2,500,000, above that the claim is escalated to the technical desk queue. | Must |
| FR-042 | A reserve change beyond the actor's authority moves the claim to `PENDING_APPROVAL` and records the pending amount. | Must |
| FR-043 | A senior handler may approve or decline a pending reserve or settlement, with a mandatory note. | Must |
| FR-044 | Settlement creates a payment instruction with payee details, amount and currency, and is only permitted from `APPROVED`. | Must |
| FR-045 | Total settled amount may not exceed the current approved indemnity reserve. | Must |

### 5.6 SLA timers

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-050 | Each claim carries SLA targets: acknowledgement 4 business hours, first contact 1 business day, decision 15 business days (30 for `COMPLEX`). | Must |
| FR-051 | The queue exposes time remaining per SLA and a breach flag; breached claims sort first. | Must |
| FR-052 | SLA clocks pause while a claim is `PENDING_APPROVAL` awaiting the customer's information (`awaiting_information` flag). | Should |

### 5.7 Audit trail

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-060 | Every state change, reserve change, document event, triage decision and payment instruction writes an immutable audit event with actor, role, correlation ID and payload digest. | Must |
| FR-061 | Audit events are queryable by claim, actor and time range, and are never updated or deleted through any API path. | Must |
| FR-062 | The auditor role has read access to every claim regardless of queue or segment ownership. | Must |

### 5.8 Notification outbox

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-070 | Outbound notifications and payment instructions are written to a transactional outbox in the same database transaction as the state change that caused them. | Must |
| FR-071 | A dispatcher publishes outbox entries at least once, with retry and a dead-letter state after five failures. | Must |
| FR-072 | Outbox entries carry the correlation ID of the originating request. | Must |

### 5.9 Security and access

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-080 | All endpoints except `/healthz`, `/readyz`, `/metrics` and the OpenAPI document require a valid bearer JWT issued by the corporate IdP. | Must |
| FR-081 | Tokens are verified for signature, issuer, audience and expiry; roles are read from the `roles` claim. | Must |
| FR-082 | Roles are `claims_handler`, `senior_handler` and `auditor`; the auditor role is read-only and is rejected on every write endpoint. | Must |
| FR-083 | Authorisation failures return `403 forbidden` with no claim data in the body. | Must |

### 5.10 API behaviour

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-090 | List endpoints are cursor-paginated with a bounded page size (default 25, maximum 100). | Must |
| FR-091 | Errors use a single structured envelope: `code`, `message`, `details`, `correlation_id`. | Must |
| FR-092 | The published OpenAPI document matches the implementation; drift fails the build. | Must |
| FR-093 | Every response carries an `X-Correlation-Id` header, echoing the request's value when supplied. | Must |

### 5.11 Ops console

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-100 | The console shows a claims queue with segment, priority, SLA state and status filters. | Must |
| FR-101 | The claim detail view shows header facts, the triage decision with rule-set version, reserve history, documents and the full timeline. | Must |
| FR-102 | Handlers can perform triage re-run, reserve proposal, approval/decline and settlement from the claim detail view, subject to their role. | Must |
| FR-103 | The audit view lists audit events for a claim with actor, role and correlation ID. | Must |
| FR-104 | The console's API client types are generated from the OpenAPI document and checked in CI. | Must |

## 6. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | p95 latency ≤ 300 ms for claim reads and ≤ 600 ms for writes at 50 requests/second. |
| NFR-002 | Availability target 99.9% monthly for the API; the console degrades to read-only if writes fail. |
| NFR-003 | All logs are structured JSON with `correlation_id`, `actor_id` and `claim_reference` where applicable, and contain no policyholder PII beyond identifiers. |
| NFR-004 | Distributed traces are emitted via OpenTelemetry (OTLP) for every request and database call. |
| NFR-005 | Prometheus metrics expose request rate, latency histograms, outbox depth and triage decisions by segment. |
| NFR-006 | Migrations are forward-only, reviewed, and must apply cleanly to an empty and to a seeded database in CI. |
| NFR-007 | No secret values in source, images or Terraform state; secrets come from the platform secret manager. |
| NFR-008 | Audit records are retained for seven years; claim documents for ten years from closure. |
| NFR-009 | The service runs as a non-root container with a read-only root filesystem. |
| NFR-010 | Test suite runs in under five minutes in CI; unit tests alone in under thirty seconds. |

## 7. Out of scope

- Policy administration, underwriting and pricing.
- The customer-facing portal and mobile app (they consume this API).
- Bank payment execution — the payments hub owns it; this service emits instructions only.
- Fraud scoring models; the platform consumes an indicator supplied on the FNOL.
- Bulk historical migration from `CLMS7`, handled by a separate load programme.
- Commercial lines and broker-originated claims.

## 8. Success measures

| Measure | Baseline | Target |
| --- | --- | --- |
| Median time to claim reference | 11 min | < 90 s |
| Duplicate claim rate | 6% | < 1.5% |
| Rule change lead time | 1 release cycle | < 1 day |
| Finance reconciliation breaks | ~40/month | < 5/month |
| Time to assemble an ombudsman evidence pack | 2–3 days | < 1 hour |

## 9. Traceability

Requirement IDs appear in code and tests. `docs/api-contract.md` maps endpoints to FR IDs, and
`services/api/tests` names each test after the requirement it covers, for example
`test_fr011_illegal_transition_rejected`.
