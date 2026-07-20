import uuid

from django.db import models


class TimesheetPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="timesheet_periods"
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_locked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "starts_on", "ends_on"], name="uq_timesheet_period"
            )
        ]


class BillingRate(models.Model):
    """Dated rates keep cost and price separate (spec G11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="billing_rates"
    )
    activity = models.CharField(max_length=64)
    hourly_cost = models.DecimalField(max_digits=10, decimal_places=2)
    hourly_price = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "activity", "valid_from"], name="uq_billing_rate_effective"
            )
        ]


class TimeEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="time_entries"
    )
    worker = models.ForeignKey(
        "foundation_accounts.Membership", on_delete=models.PROTECT, related_name="time_entries"
    )
    project = models.ForeignKey(
        "management_projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="time_entries",
    )
    activity = models.CharField(max_length=64)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    is_billable = models.BooleanField(default=True)
    status = models.CharField(max_length=16, default="draft")  # draft | approved
    correction_note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ended_at__gt=models.F("started_at")), name="ck_time_entry_duration"
            )
        ]
