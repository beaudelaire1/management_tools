from django.db import transaction

from .models import Delegation, Role, RoleAssignment


@transaction.atomic
def assign_role(*, membership_id: str, role_code: str, actor_membership_id: str | None = None) -> RoleAssignment:
    if actor_membership_id is not None and str(actor_membership_id) == str(membership_id):
        raise ValueError("Self-elevation is not allowed.")
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
) -> Delegation:
    if str(from_membership_id) == str(to_membership_id):
        raise ValueError("Self-delegation is not allowed.")
    role = Role.objects.get(code=role_code)
    return Delegation.objects.create(
        role=role,
        from_membership_id=from_membership_id,
        to_membership_id=to_membership_id,
        starts_at=starts_at,
        ends_at=ends_at,
    )
