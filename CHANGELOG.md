# Changelog

All notable changes to this project are documented in this file.
The format follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

### Security

- Bind permission decisions to an active membership, target organization, and optional data scope; cross-tenant
  dashboard and report access is denied and logged.
- Restrict role assignment and delegation to active memberships in the same organization; a delegation can no
  longer grant a role or scope the delegator does not hold.
- Reject cross-organization links in quotes, invoices, payments, dashboard widgets, objectives, and workflow
  instances.
- Protect sent quote versions, issued invoices, and their lines against ORM mutation and direct PostgreSQL writes.
- Reject idempotency-key replay when payment or notification payloads differ.

### Changed

- CI and the documented setup now install the pinned `requirements.lock` before the editable package.
- Project status documentation now distinguishes implemented baselines from complete, production-ready bricks.
- Permission delegation checks now use a correlated existence query instead of one source-assignment query per
  delegation, with a constant-query regression test.
- Permission scope types and idempotent replay comparison are centralized; PostgreSQL and ORM immutability error
  contracts are kept aligned by explicit regression tests.

### Added

- Lot 0 foundation baseline: organizations (F01 partial), accounts and invitations (F02 partial),
  roles and permissions (F03 partial), append-only audit log (F04 baseline),
  workflows with idempotent transitions (F05 baseline), versioned documents (F06 baseline),
  transactional sequences (F09 baseline).
- Foundation completion: F01 full models (BrandSettings, Address, Department, Team, legal/fiscal profiles,
  archive-without-delete), F02 sessions/MFA factors/progressive lockout, F03 data scopes, dated delegations,
  policy decision log, self-elevation prevention, F04 PostgreSQL append-only trigger,
  F07 notifications (idempotent queue, retry cap, validated templates), F08 features/settings/vocabulary,
  F10 reference data with idempotent initial load, F11 all-or-nothing imports and scoped exports,
  F12 accessible UI base templates with saved views and table preferences.
- Environment-split Django settings (local, test, production) with hardened production profile.
- CI pipeline: lint, typing, security scan, dependency audit, migration check, PostgreSQL tests, coverage gate.
- Lot 2 commercial cycle: parties with controlled merge (G01), CRM lead conversion without duplication (G02),
  dated catalog pricing (G03), versioned quotes with frozen totals and proof-based acceptance (G04),
  orders and capped deliveries (G05), immutable invoices with chronological numbering and capped credit notes (C01),
  idempotent payments with double-cap allocations (C02), aging balance, reminders and disputes (C03),
  centralized money computation shared by every document.
- Lot 3 steering: auditable indicators with deterministic formulas (P02), permission-checked dashboards (P01),
  objectives linked to measurable key results (P03), budgets with frozen approved versions and overspend
  detection (P04), dated reproducible forecasts (P05), side-effect-free scenario comparison (P06),
  sourced cash projections with low-point alerts (P07), margin and funnel analytics reconciled to sources
  (P08/P09), reproducible permission-checked reports (P13). Steering never writes to domain tables.
