# budgeting (P04)

Budgets by axis with frozen approved versions.

- Depends on: organizations (F01).
- Models: `Budget`, `BudgetVersion` (approved = frozen), `BudgetLine` (unique per axis), `BudgetActual`.
- Services: `set_budget_line` (draft only), `approve_version` (empty version rejected), `create_revision` (explicit, copies lines), `budget_availability` (budgeted/consumed/available per axis), `overspent_axes`.
- Not yet implemented: approval workflow (F05 wiring), commitments, envelope transfers, analytic axis binding (C10).
