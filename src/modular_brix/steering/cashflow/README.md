# cashflow (P07)

Short-term cash projection sourced from receivables.

- Depends on: billing (C01), payments (C02) — read-only.
- Services (no models): `expected_inflows` — one flow per open invoice (no double counting), tagged `certain`, traceable to its source number; `projected_balance_curve`; `low_point_alerts` (configurable threshold).
- Not yet implemented: outflows (supplier side, C05), probable/simulated flows, recurring items, persisted snapshots.
