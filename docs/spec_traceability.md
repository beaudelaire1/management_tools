# Specification traceability - Lot 0

## Covered sections

- 2.3 Socle technique a initialiser
- 2.4 Conditions de sortie de l'initialisation (partial)
- 4.3 Structure obligatoire d'une brique (partial)
- 4.4 Regles de modelisation communes (partial)
- 11.1 Strategie de tests (initial scope)
- 12.1 Lot 0 - Initialisation
- 5.5 F05 Workflows et validations (baseline)
- 5.6 F06 Documents, versions et signatures (baseline sans signature electronique)

## Acceptance criteria mapped

- Reproducible installation: project packaging and editable install metadata
- New database from zero: initial migration for organizations
- Modular structure: foundation app boundaries created
- Neutrality: no studio prefix in package names and runtime strings
- Testable baseline: pytest with database tests for org services and isolation policy
- Invitation-to-membership baseline: organization membership creation is validated by tests
- Explicit permission model baseline: deny-by-default and role-granted action is validated by tests
- Audit persistence baseline: auditable events are persisted with context and queryable by organization
- Workflow baseline: legal transition enforcement, requester/approver separation, and idempotent transition application
- Documents baseline: append-only version history with current marker and organization-scoped access control
- Sequences baseline (F09): atomic allocation, per-scope continuity, PostgreSQL concurrency test in CI
- Governance: LICENSE, CONTRIBUTING, CHANGELOG, CODEOWNERS, PR template, initial commit
- Environments: settings split local/test/production; production deploy check passes with --fail-level WARNING
- Dependency lock: requirements.lock generated and audited (pip-audit: no known vulnerabilities)
- Coverage gate: pytest --cov fail-under=85 (measured 99.42%)
- F01 completed: all specified models, archive without delete
- F02 extended: session revocation, MFA factor model, progressive lockout, anti-enumeration
- F03 extended: data scopes, dated delegations, policy decision log, self-elevation blocked
- F04 hardened: PostgreSQL trigger blocks UPDATE/DELETE at database level (applied in CI)
- F07/F08/F10/F11/F12 baselines implemented with acceptance-criteria tests

## Explicit limits

- Business domains (management G, finance C, steering P) are not started: next lots
- F06 signature workflows and antivirus controls are not yet implemented
- F07 preferences/suppression lists, F08 custom fields, F10 calendars/holidays, F11 mappings/encryption,
  F12 HTMX partials catalog remain to implement (documented per brick README)
- Backup/restore demonstrated with dumpdata/loaddata on the reference project only

## Regulatory references status

- Reference status is tracked in docs/references_validation.md
- Non-verified references remain explicitly marked NON VERIFIED
