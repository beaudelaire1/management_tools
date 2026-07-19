import uuid

from django.db import models


class AnalyticAxis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="analytic_axes"
    )
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_analytic_axis_code")
        ]


class AnalyticAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    axis = models.ForeignKey(AnalyticAxis, on_delete=models.CASCADE, related_name="accounts")
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["axis", "code"], name="uq_analytic_account_code")
        ]


class AnalyticAllocation(models.Model):
    """Percentage split of one general-ledger line over one axis (spec C10)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(
        "finance_ledger.JournalEntryLine", on_delete=models.PROTECT, related_name="analytic_allocations"
    )
    analytic_account = models.ForeignKey(
        AnalyticAccount, on_delete=models.PROTECT, related_name="allocations"
    )
    percent = models.DecimalField(max_digits=6, decimal_places=2)
    superseded_at = models.DateTimeField(null=True, blank=True)  # reallocation keeps history

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percent__gt=0, percent__lte=100), name="ck_allocation_percent"
            )
        ]
