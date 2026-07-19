# Changelog

All notable changes to this project are documented in this file.
The format follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Operations lot 4 (G06-G15): purchasing, append-only stock, projects, interventions, scheduling,
  time tracking, contracts and subscriptions, support, assets and maintenance, workforce administration.
- Steering lot 5 (P10-P12): capacity utilization, risk register with controls, quality CAPA.
- Pre-accounting lot 6 (C04-C07): expenses, supplier invoices with three-way matching, banking with
  idempotent imports and audited reconciliation, accountant transmission batches.
- Accounting lot 7 (C08-C13, C15): double-entry ledger, subledger lettering, analytic allocations,
  tax returns, fixed assets, closing runs, deterministic FEC exports.
- E-invoicing lot 8 (C14): frozen payloads, idempotent transmissions, pluggable platform adapters.
- Foundation completions: document signatures and file-acceptance controls (F06), notification
  suppression lists and channel preferences (F07), typed custom fields (F08), business calendars and
  holiday-aware deadlines (F10), import mappings and HMAC export seals (F11), HTMX partials (F12).
- G01 party addresses feeding the C01 buyer-address mention automatically.

## [0.1.0] - 2026-07-19

First tagged release: foundation (F01-F12), commercial cycle (G01-G05), finance baseline (C01-C03) with the
completed C01 mandatory-mention set and PDF rendering, steering (P01-P09, P13), and the configurable
server-rendered portal. The full CI quality chain (lint, typing, security scan, dependency audit, migration
checks, PostgreSQL tests with coverage gate, production deploy check) passes on a clean environment; see
`docs/etat_des_lieux.md` for the verified status report.

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

- C01 completion: full mandatory-mention snapshot frozen at invoice issuance (seller legal identity, share
  capital, registry city, addresses, VAT numbers, late-penalty rate, fixed recovery indemnity, early-discount
  terms, art. 293 B exemption for franchise regimes), `missing_mandatory_mentions` gap reporting, deterministic
  dependency-free PDF rendering that refuses drafts and incomplete mention sets, and a permission-checked
  portal download endpoint.
- Authenticated, responsive server-rendered portal with organization switching, permission-checked navigation,
  searchable resource lists, detail screens, accessible forms, and a complete quote-to-cash interaction flow.
- Reusable portal configuration with validated theme tokens, left/right/top navigation, compact density, selective
  brick installation, and external resource providers without template forks.
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
