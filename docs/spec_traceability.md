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

## Lots 4-8 acceptance criteria mapped

- G06: requester/approver separation, idempotent order conversion, receipts capped by the ordered remainder
- G07: stock computed from append-only movements, reservations never oversell, inventory gaps justified
- G08: dependency cycles rejected, blocking paths visible, computed progress, scope-change history
- G09: exactly-once stock consumption (idempotency-keyed, one-to-one with the movement), report-gated closure,
  immutable customer signatures
- G10: transactional conflict detection (bookings and absences), adjacent slots allowed
- G11: no overlaps per worker, locked periods, dated cost/price valuation, traced corrections
- G12: frozen signed versions, explicit renewals, idempotent per-period subscription billing, no silent deadline
- G13: SLA clock from priority policy, private notes separated from customer replies, traced reopening
- G14: monotonic meters, maintenance due by time or meter, per-asset cost reconciliation
- G15: audited sensitive reads, certification-gated assignments, leave approval separation
- P10: no double-counted workload, absence-adjusted capacity, overload flagged
- P11: append-only assessments, residual capped by gross, evidence-backed controls, overdue flagged
- P12: evidence-gated closure, root cause required from major severity, traced reopening, overdue actions
- C04: receipt threshold, VAT capped, duplicate detection, approver/beneficiary separation, single reimbursement
- C05: duplicate-proof identity, three-way match blocking gaps, proposals restricted to validated debts
- C06: idempotent imports, balance-consistency refusal, capped one-to-many matching, audited unmatching
- C07: per-line sources, reproducible content hash, period locking, comment resolution, missing-piece flagging
- C08: balance enforced, chronological validation numbers, ORM-frozen validated entries, reversal-only
  correction, locked periods, reconciled trial balance
- C09: balanced lettering groups, remainder caps, partial follow-up, controlled unlettering, party balances
- C10: splits total 100 percent, superseded history, ledger reconciliation, unallocated visibility
- C11: historical rates, source-reconciled returns, frozen validated returns, reasoned adjustments
- C12: plans summing exactly to base, double-posting impossible, NBV disposals
- C13: evidence-gated critical tasks, preparer/validator separation, balanced carry-forwards, audited reopening
- C14: frozen payloads, idempotent transmission, adapter swap without touching C01, divergence detection
- C15: deterministic fingerprinted FEC, imposed column order, validated entries only, sequence controls
- F06-F12 completions: immutable document signatures bound to content hashes, blocked extensions and scanner
  hooks, suppression lists and channel preferences enforced at queue time, typed custom fields with required
  checks, business-day calendar arithmetic, import mappings and HMAC export seals, HTMX partial catalogue

## Explicit limits

- Every listed brick remains a baseline until all mandatory interfaces, selectors/policies, APIs where required,
  examples, and full acceptance criteria from the specification are delivered
- The portal covers the commercial cycle; section 9 interface contracts for the new bricks (dashboards,
  list/detail templates) remain to deliver
- C14 ships a test-only reference adapter; a plateforme agréée adapter is required before production
- C08-C15 remain subject to chartered-accountant validation before any production use (spec section 15)
- C01 mention snapshot and PDF are implemented; the buyer address still lacks a source model (G01 parties carry
  no addresses) and the late-penalty rate is caller-provided; chartered-accountant validation required before production
- F06 signature workflows and antivirus controls are not yet implemented
- F07 preferences/suppression lists, F08 custom fields, F10 calendars/holidays, F11 mappings/encryption,
  F12 HTMX partials catalog remain to implement (documented per brick README)
- Backup/restore demonstrated with dumpdata/loaddata on the reference project only

## Regulatory references status

- Reference status is tracked in docs/references_validation.md
- Non-verified references remain explicitly marked NON VERIFIED
