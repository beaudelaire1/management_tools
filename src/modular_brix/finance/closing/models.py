import uuid

from django.db import models


class ClosingRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fiscal_year = models.OneToOneField(
        "finance_ledger.FiscalYear", on_delete=models.PROTECT, related_name="closing_run"
    )
    status = models.CharField(max_length=16, default="open")  # open | closed | reopened
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_count = models.PositiveIntegerField(default=0)


class ClosingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ClosingRun, on_delete=models.CASCADE, related_name="tasks")
    name = models.CharField(max_length=255)
    is_critical = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    evidence = models.CharField(max_length=500, blank=True)
    prepared_by = models.CharField(max_length=255, blank=True)
    validated_by = models.CharField(max_length=255, blank=True)


class CarryForward(models.Model):
    """Balance-sheet openings for the next year; the batch must balance (spec C13)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ClosingRun, on_delete=models.CASCADE, related_name="carry_forwards")
    account_code = models.CharField(max_length=16)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
