import uuid

from django.conf import settings
from django.db import models


class MessageTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    required_variables = models.JSONField(default=list)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    channel = models.CharField(max_length=24)  # email | sms | in_app
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=24, default="queued")  # queued | delivered | failed
    idempotency_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="uq_notification_org_idempotency",
            )
        ]


class DeliveryAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    succeeded = models.BooleanField()
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "attempt_number"],
                name="uq_delivery_attempt_number",
            )
        ]
