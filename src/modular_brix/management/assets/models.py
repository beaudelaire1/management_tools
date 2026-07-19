import uuid

from django.db import models


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="physical_assets"
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, default="in_service")  # in_service | out_of_service
    commissioned_on = models.DateField(null=True, blank=True)
    decommissioned_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_asset_org_code")
        ]


class AssetAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")
    assignee_name = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)


class MeterReading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="meter_readings")
    read_at = models.DateTimeField()
    value = models.DecimalField(max_digits=14, decimal_places=2)


class MaintenancePlan(models.Model):
    """Maintenance is due by elapsed time or by meter threshold, whichever applies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_plans")
    name = models.CharField(max_length=255)
    interval_days = models.PositiveIntegerField(null=True, blank=True)
    meter_interval = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    last_done_on = models.DateField(null=True, blank=True)
    last_done_meter = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)


class MaintenanceOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="maintenance_operations")
    plan = models.ForeignKey(
        MaintenancePlan, null=True, blank=True, on_delete=models.PROTECT, related_name="operations"
    )
    done_on = models.DateField()
    description = models.CharField(max_length=500)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
