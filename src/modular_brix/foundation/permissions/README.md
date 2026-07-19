# permissions (F03)

Explicit roles and action permissions, deny by default.

- Depends on: accounts (F02).
- Models: `Role`, `RoleAssignment`, `DataScope`, `Delegation` (dated and scope-bounded), `PolicyDecisionLog` (target organization, scope, decision, and reason).
- Policies: `has_action_permission` — deny by default; requires an active membership in the target organization and enforces organization/establishment/team/object scopes for direct and delegated roles.
- Services: `assign_role` requires either an authorized actor or an explicit trusted-system bootstrap context and blocks inactive, self, unauthorized, and cross-organization elevation; `delegate_role` requires the giver to retain the role and prevents scope broadening.
- Not yet implemented: reusable scope-filtered queryset helpers and access simulator UI.
