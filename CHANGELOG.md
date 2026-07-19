# Changelog

All notable changes to this project are documented in this file.
The format follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

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
