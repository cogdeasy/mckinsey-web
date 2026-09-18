# ADR 0002: Python, FastAPI and Postgres for the claims API

- Status: Accepted
- Date: 2026-08-06
- Deciders: Claims Platform engineering

## Context

The claims API is a transactional, integration-heavy service: FNOL capture, a state machine,
money amounts, an outbox and a large surface of contract-tested endpoints. The wider Meridian
estate runs Java (policy admin) and Python (data and pricing). The claims team's existing
skills are Python, and the fraud indicator and pricing services already expose Python clients.

Alternatives considered:

1. Java 21 + Spring Boot — best fit with policy admin, but no team capacity and slower local
   iteration for the rules work.
2. Node.js + NestJS — shares a language with the console, but weaker numeric and migration
   story for money handling.
3. Python 3.12 + FastAPI + SQLAlchemy 2.x.

## Decision

Python 3.12 with FastAPI, Pydantic v2 for request/response models, SQLAlchemy 2.x with the
typed ORM and Alembic for migrations, on managed PostgreSQL 16.

Money is stored as integer minor units with an ISO 4217 currency column. No floating point is
used for monetary values at any layer.

## Consequences

- OpenAPI is generated from the same Pydantic models the handlers use, so the contract cannot
  silently drift; a CI check asserts the committed schema matches.
- `mypy --strict` is viable because SQLAlchemy 2.x models are typed.
- Cross-team code sharing with the Java estate is limited to the HTTP contract.
