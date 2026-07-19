from django.db import models
from django.utils import timezone

from .models import Delegation, PolicyDecisionLog, RoleAssignment


ACTION_FIELD_MAP = {
    "read": "can_read",
    "create": "can_create",
    "validate": "can_validate",
    "export": "can_export",
}


def has_action_permission(*, membership_id: str, action: str) -> bool:
    """Deny by default; every decision is recorded in the policy decision log."""
    field_name = ACTION_FIELD_MAP.get(action)
    now = timezone.now()

    if field_name is None:
        allowed, reason = False, "unknown_action"
    else:
        direct = (
            RoleAssignment.objects.filter(membership_id=membership_id)
            .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))
            .filter(**{f"role__{field_name}": True})
            .exists()
        )
        delegated = Delegation.objects.filter(
            to_membership_id=membership_id,
            starts_at__lte=now,
            ends_at__gte=now,
            **{f"role__{field_name}": True},
        ).exists()
        allowed = direct or delegated
        reason = "role" if direct else ("delegation" if delegated else "no_grant")

    PolicyDecisionLog.objects.create(
        membership_id=membership_id,
        action=action,
        allowed=allowed,
        reason=reason,
    )
    return allowed
