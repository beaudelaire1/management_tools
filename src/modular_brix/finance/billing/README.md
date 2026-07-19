# billing (C01)

Invoices and credit notes with regulatory-grade immutability.

- Depends on: sales (G04/G05), parties (G01), sequences (F09); totals via `modular_brix.common.money`.
- Models: `Invoice` — draft then irreversible issuance; ORM guards and PostgreSQL triggers make an issued invoice and its lines non-modifiable and non-deletable; seller/buyer snapshots frozen at issuance; partial unique constraint on number. `InvoiceLine`, `CreditNote` (positive, capped).
- Services: `create_invoice_from_order` (idempotent), `issue_invoice` (chronological continuous number per organization/year via F09), `create_credit_note` (never exceeds the creditable remainder), `invoice_remaining`.
- Compliance note: mandatory invoice mentions (SIREN, operation category, VAT options — spec S1/S2) are prepared at the snapshot level but the full mention set and PDF layout remain to implement; validation by a chartered accountant is required before production use.
