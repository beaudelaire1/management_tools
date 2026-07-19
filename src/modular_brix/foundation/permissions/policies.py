from django.db import models
from django.utils import timezone

from modular_brix.foundation.accounts.models import Membership

from .models import Delegation, PolicyDecisionLog, RoleAssignment


ACTION_FIELD_MAP = {
    "read": "can_read",
    "create": "can_create",
    "validate": "can_validate",
    "export": "can_export",
    "manage_permissions": "can_manage_permissions",
}


def _scope_matches(*, scope_type: str, scope_ref: str, organization_id: str) -> models.Q:
    organization_scope = models.Q(data_scopes__scope_type="organization", data_scopes__scope_ref=organization_id)
    unscoped = models.Q(data_scopes__isnull=True)
    if not scope_type or not scope_ref:
        return unscoped | organization_scope
    return unscoped | organization_scope | models.Q(
        data_scopes__scope_type=scope_type,
        data_scopes__scope_ref=scope_ref,
    )


def _delegation_scope_matches(*, scope_type: str, scope_ref: str, organization_id: str) -> models.Q:
    organization_scope = models.Q(scope_type="organization", scope_ref=organization_id)
    unscoped = models.Q(scope_type="", scope_ref="")
    if not scope_type or not scope_ref:
        return unscoped | organization_scope
    return unscoped | organization_scope | models.Q(scope_type=scope_type, scope_ref=scope_ref)


def has_action_permission(
    *,
    membership_id: str,
    action: str,
    organization_id: str,
    scope_type: str = "",
    scope_ref: str = "",
) -> bool:
    """Deny by default and bind every grant to an active membership and data scope."""
    field_name = ACTION_FIELD_MAP.get(action)
    now = timezone.now()
    membership = Membership.objects.filter(id=membership_id).first()

    if membership is None:
        return False

    if field_name is None:
        allowed, reason = False, "unknown_action"
    elif not membership.is_active:
        allowed, reason = False, "inactive_membership"
    elif str(membership.organization_id) != str(organization_id):
        allowed, reason = False, "organization_mismatch"
    else:
        direct = (
            RoleAssignment.objects.filter(membership_id=membership_id)
            .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))
            .filter(**{f"role__{field_name}": True})
            .filter(
                _scope_matches(
                    scope_type=scope_type,
                    scope_ref=scope_ref,
                    organization_id=str(organization_id),
                )
            )
            .exists()
        )
        delegation_candidates = Delegation.objects.filter(
            to_membership_id=membership_id,
            from_membership__organization_id=organization_id,
            to_membership__organization_id=organization_id,
            from_membership__is_active=True,
            to_membership__is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
            **{f"role__{field_name}": True},
        ).filter(
            _delegation_scope_matches(
                scope_type=scope_type,
                scope_ref=scope_ref,
                organization_id=str(organization_id),
            )
        )
        delegated = False
        for delegation in delegation_candidates:
            source_assignments = (
                RoleAssignment.objects.filter(
                    membership=delegation.from_membership,
                    role=delegation.role,
                )
                .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
                .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))
                .filter(
                    _scope_matches(
                        scope_type=delegation.scope_type,
                        scope_ref=delegation.scope_ref,
                        organization_id=str(organization_id),
                    )
                )
            )
            if source_assignments.exists():
                delegated = True
                break
        allowed = direct or delegated
        reason = "role" if direct else ("delegation" if delegated else "no_grant")

    PolicyDecisionLog.objects.create(
        membership_id=membership_id,
        action=action,
        target_organization_id=organization_id,
        scope_type=scope_type,
        scope_ref=scope_ref,
        allowed=allowed,
        reason=reason,
    )
    return allowed
