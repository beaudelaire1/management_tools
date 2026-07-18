from django.db import models
from django.utils import timezone

from .models import RoleAssignment


ACTION_FIELD_MAP = {
    "read": "can_read",
    "create": "can_create",
    "validate": "can_validate",
    "export": "can_export",
}


def has_action_permission(*, membership_id: str, action: str) -> bool:
    field_name = ACTION_FIELD_MAP.get(action)
    if field_name is None:
        return False

    now = timezone.now()
    assignment_qs = RoleAssignment.objects.filter(
        membership_id=membership_id,
    ).filter(
        models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now)
    ).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
    )
    return assignment_qs.filter(**{f"role__{field_name}": True}).exists()
