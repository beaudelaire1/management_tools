# ADR 0001 — Modular monolith with a neutral namespace

Date: 2026-07-18. Status: accepted.

## Context

The specification mandates a modular Django monolith delivered as installable, client-neutral bricks (spec §1, §4.1).
The normative layout names the first layer `platform/`, which collides with the Python standard library module `platform`.

## Decision

- Single package rooted at `src/modular_brix` with domain sub-packages (`foundation` first).
- The logical layer required by the specification is preserved; only the top-level Python name differs to avoid the stdlib collision.
- Django app labels are prefixed by layer (`foundation_organizations`, ...) to prevent label collisions in client projects.

## Consequences

- Stable imports, selective installation per app.
- `manage.py makemigrations` must use app labels, not directory names.
