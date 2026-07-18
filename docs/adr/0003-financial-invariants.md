# ADR 0003 — Financial-grade invariants enforced in services and constraints

Date: 2026-07-18. Status: accepted.

## Context

Spec §4.4 and §11.2 require immutability of validated financial records, idempotent processing, and database-level constraints.

## Decision

- Audit events are append-only at the ORM layer (guarded `save`/`delete`); a PostgreSQL trigger will complete the guarantee.
- Regulatory document versions require an explicit `allow_regulatory_replacement` flag (no silent replacement).
- Workflow transitions are idempotent via a unique `(instance, idempotency_key)` constraint; definitions with running instances are frozen.
- Document numbering (F09) allocates under `SELECT FOR UPDATE` with a unique `(organization, code, period)` scope; concurrency is tested on PostgreSQL in CI.

## Consequences

- Business rules are testable and duplicated at the database layer where possible.
- SQLite is acceptable for unit tests only; concurrency guarantees are validated on PostgreSQL.
