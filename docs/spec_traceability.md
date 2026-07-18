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

## Explicit limits

- PostgreSQL runtime is not yet wired in local default settings (SQLite dev default only)
- Foundation F05-F12 and business domains are still scaffold-level or absent
- F06 signature workflows and antivirus controls are not yet implemented
- Security headers, MFA, and external secret manager are not yet implemented in this increment

## Regulatory references status

- Reference status is tracked in docs/references_validation.md
- Non-verified references remain explicitly marked NON VERIFIED
