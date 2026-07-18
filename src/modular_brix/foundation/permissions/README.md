# permissions (F03)

Explicit roles and action permissions, deny by default.

- Depends on: accounts (F02).
- Models: `Role` (read/create/validate/export flags), `RoleAssignment` (optional validity window).
- Policies: `has_action_permission` — returns False unless a currently-valid assignment grants the action.
- Not yet implemented: `DataScope`, `Delegation`, `PolicyDecisionLog`, self-elevation prevention.
