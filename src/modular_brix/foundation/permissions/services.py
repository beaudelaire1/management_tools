from django.db import models, transaction

from modular_brix.foundation.accounts.models import Membership

from .models import Delegation, Role, RoleAssignment, ScopeType


@transaction.atomic
def assign_role(
    *,
    membership_id: str,
    role_code: str,
    actor_membership_id: str | None = None,
    trusted_system: bool = False,
) -> RoleAssignment:
    if actor_membership_id is None and not trusted_system:
        raise PermissionError("Role assignment requires an authorized actor or an explicit trusted-system context.")
    if actor_membership_id is not None and trusted_system:
        raise ValueError("Choose either an acting membership or the trusted-system context, not both.")
    if actor_membership_id is not None and str(actor_membership_id) == str(membership_id):
        raise ValueError("Self-elevation is not allowed.")
    membership = Membership.objects.select_related("organization").get(id=membership_id)
    if not membership.is_active:
        raise ValueError("A role cannot be assigned to an inactive membership.")
    if actor_membership_id is not None:
        actor_membership = Membership.objects.get(id=actor_membership_id)
        if not actor_membership.is_active:
            raise ValueError("An inactive membership cannot assign roles.")
        if actor_membership.organization_id != membership.organization_id:
            raise ValueError("Roles cannot be assigned across organizations.")
        from .policies import has_action_permission

        if not has_action_permission(
            membership_id=str(actor_membership.id),
            action="manage_permissions",
            organization_id=str(membership.organization_id),
        ):
            raise PermissionError("The acting membership cannot manage permissions.")
    role = Role.objects.get(code=role_code)
    assignment, _ = RoleAssignment.objects.get_or_create(
        membership_id=membership_id,
        role=role,
    )
    return assignment


@transaction.atomic
def delegate_role(
    *,
    role_code: str,
    from_membership_id: str,
    to_membership_id: str,
    starts_at,
    ends_at,
    scope_type: str = "",
    scope_ref: str = "",
) -> Delegation:
    if str(from_membership_id) == str(to_membership_id):
        raise ValueError("Self-delegation is not allowed.")
    if ends_at <= starts_at:
        raise ValueError("Delegation end must be after its start.")
    if bool(scope_type) != bool(scope_ref):
        raise ValueError("Delegation scope type and reference must be provided together.")
    if scope_type and scope_type not in ScopeType.values:
        raise ValueError(f"Unsupported delegation scope type: {scope_type}.")

    memberships = {
        str(membership.id): membership
        for membership in Membership.objects.select_related("organization").filter(
            id__in=[from_membership_id, to_membership_id]
        )
    }
    giver = memberships.get(str(from_membership_id))
    recipient = memberships.get(str(to_membership_id))
    if giver is None or recipient is None:
        raise ValueError("Both delegation memberships must exist.")
    if not giver.is_active or not recipient.is_active:
        raise ValueError("Delegations require active memberships.")
    if giver.organization_id != recipient.organization_id:
        raise ValueError("Roles cannot be delegated across organizations.")

    role = Role.objects.get(code=role_code)
    assignment = (
        RoleAssignment.objects.filter(membership=giver, role=role)
        .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=starts_at))
        .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=ends_at))
        .first()
    )
    if assignment is None:
        raise ValueError("A role can only be delegated by a membership that currently holds it.")
    if assignment.starts_at is not None and starts_at < assignment.starts_at:
        raise ValueError("A delegation cannot start before the source role assignment.")
    if assignment.ends_at is not None and ends_at > assignment.ends_at:
        raise ValueError("A delegation cannot outlive the source role assignment.")

    assignment_scopes = assignment.data_scopes.all()
    if assignment_scopes.exists():
        if not scope_type or not scope_ref:
            raise ValueError("A scoped role must be delegated with an explicit permitted scope.")
        if not assignment_scopes.filter(scope_type=scope_type, scope_ref=scope_ref).exists():
            raise ValueError("A delegation cannot exceed the source role data scope.")

    return Delegation.objects.create(
        role=role,
        from_membership_id=from_membership_id,
        to_membership_id=to_membership_id,
        starts_at=starts_at,
        ends_at=ends_at,
        scope_type=scope_type,
        scope_ref=scope_ref,
    )
