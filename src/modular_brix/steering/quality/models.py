import uuid

from django.db import models


class NonConformity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="non_conformities"
    )
    reference = models.CharField(max_length=128, blank=True)  # source object (ticket, intervention, ...)
    description = models.CharField(max_length=500)
    severity = models.CharField(max_length=16)  # minor | major | critical
    root_cause = models.CharField(max_length=500, blank=True)
    cost_of_non_quality = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=16, default="open")  # open | closed
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_count = models.PositiveIntegerField(default=0)


class CorrectiveAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    non_conformity = models.ForeignKey(NonConformity, on_delete=models.CASCADE, related_name="actions")
    description = models.CharField(max_length=500)
    kind = models.CharField(max_length=16, default="corrective")  # corrective | preventive
    due_date = models.DateField()
    done_at = models.DateTimeField(null=True, blank=True)
    evidence = models.CharField(max_length=500, blank=True)
