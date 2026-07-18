import uuid

from django.conf import settings
from django.db import models


class WorkflowDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_definitions",
    )
    code = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="uq_workflow_def_org_code_version",
            )
        ]


class WorkflowState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name="states",
    )
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=120)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "code"],
                name="uq_workflow_state_def_code",
            )
        ]


class WorkflowTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        related_name="transitions",
    )
    code = models.SlugField(max_length=80)
    source_state = models.ForeignKey(
        WorkflowState,
        on_delete=models.PROTECT,
        related_name="outgoing_transitions",
    )
    target_state = models.ForeignKey(
        WorkflowState,
        on_delete=models.PROTECT,
        related_name="incoming_transitions",
    )
    require_separate_approver = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "code"],
                name="uq_workflow_transition_def_code",
            )
        ]


class WorkflowInstance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_instances",
    )
    definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    current_state = models.ForeignKey(
        WorkflowState,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64)
    requester_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requested_workflow_instances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "object_type", "object_id", "definition"],
                name="uq_workflow_instance_object",
            )
        ]


class ApprovalDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    transition = models.ForeignKey(
        WorkflowTransition,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="workflow_decisions",
    )
    decision = models.CharField(max_length=24)
    comment = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instance", "idempotency_key"],
                name="uq_approval_decision_idempotency",
            )
        ]
