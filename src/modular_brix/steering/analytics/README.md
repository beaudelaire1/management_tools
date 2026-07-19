# analytics (P08 + P09)

Profitability and sales funnel projections, reconciled to sources.

- Depends on: billing (C01), crm (G02), sales (G04/G05) — read-only.
- Services (no models): `margin_by_party` — revenue from issued invoices, reconciliation flag against the source total; `sales_funnel` — leads/opportunities/quotes/orders/invoices reconciliation; `loss_reasons`.
- Not yet implemented: allocation rules (versioned), margin bridge, pipeline snapshots over time, customer concentration.
