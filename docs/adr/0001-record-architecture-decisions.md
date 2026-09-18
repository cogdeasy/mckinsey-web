# ADR 0001: Record architecture decisions

- Status: Accepted
- Date: 2026-08-04
- Deciders: Claims Platform engineering, Claims Technical

## Context

The claims intake platform is built by three teams over several quarters and is subject to
regulatory review. Decisions taken early (state machine ownership, storage of documents, how
rules are versioned) are expensive to revisit and need an auditable rationale.

## Decision

We keep lightweight architecture decision records in `docs/adr/`, numbered sequentially, in the
format proposed by Michael Nygard. An ADR is raised in the pull request that implements the
decision. ADRs are immutable once accepted; a later ADR supersedes an earlier one.

## Consequences

- Reviewers can see why a shape was chosen without reading commit archaeology.
- Compliance evidence packs can cite ADRs directly.
- A superseded ADR stays in the repository with a pointer to its replacement.
