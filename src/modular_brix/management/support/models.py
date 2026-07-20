import uuid

from django.db import models


class SLAPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="sla_policies"
    )
    priority = models.CharField(max_length=16)  # low | normal | high | critical
    resolution_hours = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "priority"], name="uq_sla_policy_priority")
        ]


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="tickets"
    )
    party = models.ForeignKey("management_parties.Party", on_delete=models.PROTECT, related_name="tickets")
    subject = models.CharField(max_length=255)
    priority = models.CharField(max_length=16, default="normal")
    status = models.CharField(max_length=16, default="open")  # open | resolved | closed
    sla_due_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reopened_count = models.PositiveIntegerField(default=0)


class TicketMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author_name = models.CharField(max_length=255)
    body = models.TextField()
    is_private = models.BooleanField(default=False)  # private notes never reach the customer
    sent_at = models.DateTimeField(auto_now_add=True)
