from django.db import transaction

from .models import Role, RoleAssignment


@transaction.atomic
def assign_role(*, membership_id: str, role_code: str) -> RoleAssignment:
    role = Role.objects.get(code=role_code)
    assignment, _ = RoleAssignment.objects.get_or_create(
        membership_id=membership_id,
        role=role,
    )
    return assignment
