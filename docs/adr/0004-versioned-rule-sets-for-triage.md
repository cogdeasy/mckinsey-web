# ADR 0004: Versioned declarative rule sets for triage

- Status: Accepted
- Date: 2026-08-14
- Deciders: Claims Technical, Claims Platform engineering

## Context

Triage and routing change more often than the rest of the platform, and the Claims Technical
team owns the logic. FR-020 to FR-024 require that a decision can be explained months later by
the exact rule set that produced it.

Alternatives considered: a third-party business rules engine (heavy, licensed, opaque to
version control), rules as Python code (fast, but every change is a deployment and diffing the
behaviour is hard), rules as versioned declarative data (chosen).

## Decision

Rule sets are YAML documents with a semantic version, an ordered list of rules, and a mandatory
default. Each rule has an `id`, a set of conditions over a fixed, documented fact schema, and
an outcome (segment, priority, queue). The evaluator is first-match-wins and pure. The rule set
version is persisted on every triage decision.

The fact schema is closed: a rule referencing an unknown fact fails rule set validation at load
time, which runs in CI and at service start.

## Consequences

- A rule change is a data change reviewed in the same pull request flow, deployable within a
  day rather than a release cycle.
- Decisions are reproducible: given the claim facts and the version, the outcome is derivable.
- Expressiveness is deliberately limited to comparisons and set membership; anything richer
  goes to the `SPECIAL_INVESTIGATION` segment for human handling.
