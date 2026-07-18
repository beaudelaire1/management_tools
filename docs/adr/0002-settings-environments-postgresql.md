# ADR 0002 — Environment-split settings, PostgreSQL required in production

Date: 2026-07-18. Status: accepted.

## Context

Spec §2.3 requires per-environment configuration, external secrets, and startup checks; §2.2 designates PostgreSQL as the reference database; §10.1 requires hardened production settings.

## Decision

- Settings split into `base` / `local` / `test` / `production` modules.
- Production fails to start unless `DJANGO_SECRET_KEY` (min 50 chars), `DJANGO_ALLOWED_HOSTS`, and PostgreSQL env vars are provided.
- Production enables SSL redirect, secure cookies, HSTS (1 year, preload), nosniff, and X-Frame-Options DENY; verified by `manage.py check --deploy --fail-level WARNING` in CI.
- Local development may fall back to SQLite; CI integration tests run against PostgreSQL 16.

## Consequences

- No secret with production value exists in the repository.
- `check --deploy` warnings on the local profile are expected and not a conformity signal.
