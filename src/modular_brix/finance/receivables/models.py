import uuid

from django.db import models


class Dispute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        "finance_billing.Invoice",
        on_delete=models.PROTECT,
        related_name="disputes",
    )
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="open")  # open | resolved
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class Reminder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        "finance_billing.Invoice",
        on_delete=models.PROTECT,
        related_name="reminders",
    )
    level = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)
