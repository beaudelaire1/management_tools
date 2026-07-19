# permissions (F03)

Explicit roles and action permissions, deny by default.

- Depends on: accounts (F02).
- Models: `Role`, `RoleAssignment`, `DataScope`, `Delegation` (dated, self-delegation blocked), `PolicyDecisionLog` (every decision logged with reason).
- Policies: `has_action_permission` — deny by default; grants via role or currently-valid delegation; decision + reason logged.
- Services: `assign_role` (self-elevation blocked), `delegate_role`.
- Not yet implemented: scope-filtered querysets helpers, access simulator UI.
