# Changelog

All notable changes to this project are documented in this file.
The format follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Lot 0 foundation baseline: organizations (F01 partial), accounts and invitations (F02 partial),
  roles and permissions (F03 partial), append-only audit log (F04 baseline),
  workflows with idempotent transitions (F05 baseline), versioned documents (F06 baseline),
  transactional sequences (F09 baseline).
- Environment-split Django settings (local, test, production) with hardened production profile.
- CI pipeline: lint, typing, security scan, dependency audit, migration check, PostgreSQL tests, coverage gate.
