# Specification traceability - implemented baselines

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
- Explicit permission model: deny-by-default, active membership, organization isolation, data-scope enforcement,
  bounded delegation, and logged decisions are validated by tests
- Audit persistence baseline: auditable events are persisted with context and queryable by organization
- Workflow baseline: legal transition enforcement, requester/approver separation, and idempotent transition application
- Documents baseline: append-only version history with current marker and organization-scoped access control
- Sequences baseline (F09): atomic allocation, per-scope continuity, PostgreSQL concurrency test in CI
- Governance: LICENSE, CONTRIBUTING, CHANGELOG, CODEOWNERS, PR template, initial commit
- Environments: settings split local/test/production; production deploy check passes with --fail-level WARNING
- Dependency lock: requirements.lock generated and audited (pip-audit: no known vulnerabilities)
- Coverage gate: pytest --cov fail-under=85 (measured 96.63% after the review follow-up)
- F01 completed: all specified models, archive without delete
- F02 extended: session revocation, MFA factor model, progressive lockout, anti-enumeration
- F03 extended: data scopes, dated delegations, policy decision log, self-elevation blocked
- F04 hardened: PostgreSQL trigger blocks UPDATE/DELETE at database level (applied in CI)
- F07/F08/F10/F11/F12 baselines implemented with acceptance-criteria tests
- Lot 2 (G01-G05, C01-C03) baselines implemented; invariants 11.2 tested: issued invoice immutable with frozen
  snapshot and continuous chronological numbering, credit note capped, payment allocation double-capped,
  identical monetary totals across quote/order/invoice, idempotent conversions and webhook replay,
  reminders excluding paid and disputed invoices; end-to-end path quote->order->invoice->payment reconciled (13.2-4)
- Lot 3 (P01-P09, P13) baselines implemented: widgets never bypass permissions, deterministic indicator
  computation with tracked origin, objective requires measurable key result, approved budget frozen with
  explicit revisions, forecast versions reproducible with stored assumptions, scenario comparison without
  side effects, cash flows individually sourced without double counting, margins reconciled to invoice source,
  funnel reconciliation, reports permission-checked and reproducible; steering reads domains, never writes
- Consolidation: target-organization checks prevent cross-tenant access and relationships; sent quotes, issued
  invoices, and their lines are immutable at the ORM layer and through PostgreSQL triggers; replayed payment and
  notification idempotency keys require identical payloads
- C01 completion: full mandatory-mention snapshot frozen at issuance (seller legal identity, addresses, VAT
  numbers, payment-term mentions, art. 293 B exemption), gap reporting via `missing_mandatory_mentions`, and
  deterministic dependency-free PDF rendering that refuses drafts and incomplete mention sets; portal download
  endpoint with permission checks; validated by `tests/test_invoice_compliance.py`

## Explicit limits

- Every listed brick remains a baseline until all mandatory interfaces, selectors/policies, APIs where required,
  examples, and full acceptance criteria from the specification are delivered
- Operations (G06-G15, P10-P12), pre-accounting and accounting (C04-C15) are not started: next lots
- C01 mention snapshot and PDF are implemented; the buyer address still lacks a source model (G01 parties carry
  no addresses) and the late-penalty rate is caller-provided; chartered-accountant validation required before production
- F06 signature workflows and antivirus controls are not yet implemented
- F07 preferences/suppression lists, F08 custom fields, F10 calendars/holidays, F11 mappings/encryption,
  F12 HTMX partials catalog remain to implement (documented per brick README)
- Backup/restore demonstrated with dumpdata/loaddata on the reference project only

## Regulatory references status

- Reference status is tracked in docs/references_validation.md
- Non-verified references remain explicitly marked NON VERIFIED
