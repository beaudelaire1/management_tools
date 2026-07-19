import uuid

from django.db import models


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    can_read = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_validate = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    can_manage_permissions = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class RoleAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(
        "foundation_accounts.Membership",
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role"],
                name="uq_role_assignment_membership_role",
            )
        ]


class DataScope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_assignment = models.ForeignKey(RoleAssignment, on_delete=models.CASCADE, related_name="data_scopes")
    scope_type = models.CharField(max_length=24)  # organization | establishment | team | object
    scope_ref = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role_assignment", "scope_type", "scope_ref"],
                name="uq_data_scope_assignment_ref",
            ),
            models.CheckConstraint(
                condition=models.Q(scope_type__in=["organization", "establishment", "team", "object"]),
                name="ck_data_scope_type_supported",
            ),
        ]


class Delegation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="delegations")
    from_membership = models.ForeignKey(
        "foundation_accounts.Membership",
        on_delete=models.CASCADE,
        related_name="delegations_given",
    )
    to_membership = models.ForeignKey(
        "foundation_accounts.Membership",
        on_delete=models.CASCADE,
        related_name="delegations_received",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    scope_type = models.CharField(max_length=24, blank=True)
    scope_ref = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="ck_delegation_dates_ordered",
            ),
            models.CheckConstraint(
                condition=(models.Q(scope_type="", scope_ref="") | (~models.Q(scope_type="") & ~models.Q(scope_ref=""))),
                name="ck_delegation_scope_complete",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scope_type="")
                    | models.Q(scope_type__in=["organization", "establishment", "team", "object"])
                ),
                name="ck_delegation_scope_type_supported",
            ),
        ]


class PolicyDecisionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(
        "foundation_accounts.Membership",
        on_delete=models.CASCADE,
        related_name="policy_decisions",
    )
    action = models.CharField(max_length=24)
    target_organization = models.ForeignKey(
        "foundation_organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="policy_decisions_targeting_organization",
    )
    scope_type = models.CharField(max_length=24, blank=True)
    scope_ref = models.CharField(max_length=64, blank=True)
    allowed = models.BooleanField()
    reason = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["membership", "action"], name="idx_policy_log_membership"),
            models.Index(fields=["target_organization", "action"], name="idx_policy_log_target_org"),
        ]
