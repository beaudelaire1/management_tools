import uuid

from django.db import models


class UtilizationSnapshot(models.Model):
    """Weekly capacity vs planned workload, computed from scheduling data (spec P10).

    Steering never writes to domain tables; snapshots only store derived numbers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="utilization_snapshots"
    )
    resource = models.ForeignKey(
        "management_scheduling.Resource", on_delete=models.PROTECT, related_name="utilization_snapshots"
    )
    week_start = models.DateField()
    available_hours = models.DecimalField(max_digits=8, decimal_places=2)
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "week_start"], name="uq_utilization_resource_week"
            )
        ]
