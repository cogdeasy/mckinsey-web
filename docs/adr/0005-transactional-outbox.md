# ADR 0005: Transactional outbox for notifications and payment instructions

- Status: Accepted
- Date: 2026-08-20
- Deciders: Claims Platform engineering, Payments Hub

## Context

Settlement must notify the payments hub, and lifecycle events must notify the customer
communications service. Publishing from inside a request handler either loses messages when the
broker is unavailable or produces messages for transactions that later roll back. The nightly
reconciliation breaks that finance reports today come from exactly this failure mode.

## Decision

Side effects are written to an `outbox_entry` table in the same transaction as the state
change (FR-070). A dispatcher polls unsent entries in creation order, publishes them, and marks
them sent; after five failed attempts an entry moves to `DEAD_LETTER` and raises an alert. The
correlation ID of the originating request travels with the entry.

Delivery is at-least-once; consumers deduplicate on the entry's UUID.

## Consequences

- No message is emitted for a rolled-back transaction, and no state change is silently
  unpublished.
- Outbox depth and dead-letter count are first-class metrics (NFR-005).
- The dispatcher is a separate process so that request latency is unaffected by broker health.
