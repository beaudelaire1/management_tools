# billing (C01)

Invoices and credit notes with regulatory-grade immutability.

- Depends on: sales (G04/G05), parties (G01), sequences (F09); totals via `modular_brix.common.money`.
- Models: `Invoice` — draft then irreversible issuance; ORM guards and PostgreSQL triggers make an issued invoice and its lines non-modifiable and non-deletable; seller/buyer snapshots frozen at issuance; partial unique constraint on number. `InvoiceLine`, `CreditNote` (positive, capped).
- Services: `create_invoice_from_order` (idempotent), `issue_invoice` (chronological continuous number per organization/year via F09; freezes the full mandatory-mention snapshot from the organization's legal/fiscal profiles, billing address, party VAT identifier, and caller-provided payment terms), `missing_mandatory_mentions` (reports snapshot gaps), `create_credit_note` (never exceeds the creditable remainder), `invoice_remaining`.
- PDF: `pdf.render_invoice_pdf` renders an issued invoice deterministically (byte-identical output, no external dependency, uncompressed streams) with seller/buyer blocks, line table with pagination, per-rate VAT breakdown reusing `common.money` rounding, late-penalty rate, the fixed recovery indemnity, early-discount terms, and the art. 293 B exemption mention for franchise regimes. Rendering refuses drafts and incomplete mention sets. The portal exposes the download at `invoices/<id>/pdf/`.
- Compliance note: the buyer address has no source model yet (G01 parties carry no addresses) and must be passed to `issue_invoice`; the late-penalty rate is caller-provided because the legal reference rate changes over time. Validation by a chartered accountant remains required before production use.
