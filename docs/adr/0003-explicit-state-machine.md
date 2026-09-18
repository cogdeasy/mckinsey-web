# ADR 0003: Claim lifecycle as an explicit, table-driven state machine

- Status: Accepted
- Date: 2026-08-11
- Deciders: Claims Platform engineering, Claims Technical

## Context

`CLMS7` encodes the claim lifecycle as status codes checked ad hoc at every call site. The
resulting behaviour is impossible to enumerate, and defects reach production as claims stuck in
impossible states. FR-010 to FR-014 require enumerable, auditable transitions.

## Decision

The lifecycle lives in one module (`domain/state_machine.py`) as a mapping from source state to
the set of permitted target states, together with the reason codes each transition requires.
All mutation paths call `assert_transition_allowed` before persisting, and every applied
transition writes a `claim_transition` row and an audit event in the same database transaction.

## Consequences

- The permitted transition graph is unit-testable without a database and is rendered into the
  API contract documentation.
- Adding a state is a single reviewed change plus a migration for the enum.
- Services must not set `claim.status` directly; a lint-enforced convention keeps assignment
  inside the state machine module.
