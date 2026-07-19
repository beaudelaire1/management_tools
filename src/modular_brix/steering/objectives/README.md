# objectives (P03)

Objectives linked to measurable results.

- Depends on: indicators (P02).
- Models: `Objective` (owner and horizon mandatory), `KeyResult` (linked to an indicator, positive target).
- Services: `activate_objective` (requires at least one key result), `objective_progress` (capped ratio average), `is_objective_late`.
- Not yet implemented: action plans, frozen reviews, revision history.
