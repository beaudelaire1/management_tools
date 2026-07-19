from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Asset, MaintenanceOperation, MaintenancePlan, MeterReading


@transaction.atomic
def record_meter_reading(*, asset_id: str, read_at: datetime, value: Decimal) -> MeterReading:
    """Meter readings only move forward; a regression means a data error, not usage."""
    asset = Asset.objects.select_for_update().get(id=asset_id)
    last = asset.meter_readings.order_by("-read_at").first()
    if last is not None and value < last.value:
        raise ValueError(f"A meter reading cannot decrease (last recorded: {last.value}).")
    return MeterReading.objects.create(asset=asset, read_at=read_at, value=value)


def maintenance_due(*, plan_id: str, on_day: date | None = None) -> bool:
    plan = MaintenancePlan.objects.select_related("asset").get(id=plan_id)
    today = on_day or timezone.now().date()
    if plan.interval_days is not None:
        reference = plan.last_done_on or plan.asset.commissioned_on
        if reference is not None and today >= reference + timedelta(days=plan.interval_days):
            return True
    if plan.meter_interval is not None:
        latest = plan.asset.meter_readings.order_by("-read_at").first()
        baseline = plan.last_done_meter or Decimal("0")
        if latest is not None and latest.value - baseline >= plan.meter_interval:
            return True
    return False


@transaction.atomic
def record_maintenance(
    *, asset_id: str, description: str, done_on: date, plan_id: str | None = None, cost: Decimal = Decimal("0")
) -> MaintenanceOperation:
    operation = MaintenanceOperation.objects.create(
        asset_id=asset_id, plan_id=plan_id, done_on=done_on, description=description, cost=cost
    )
    if plan_id is not None:
        plan = MaintenancePlan.objects.select_for_update().get(id=plan_id)
        plan.last_done_on = done_on
        latest = plan.asset.meter_readings.order_by("-read_at").first()
        if latest is not None:
            plan.last_done_meter = latest.value
        plan.save(update_fields=["last_done_on", "last_done_meter"])
    return operation


@transaction.atomic
def decommission_asset(*, asset_id: str, on_day: date) -> Asset:
    asset = Asset.objects.select_for_update().get(id=asset_id)
    if asset.status == "out_of_service":
        raise ValueError("This asset is already out of service.")
    asset.status = "out_of_service"
    asset.decommissioned_on = on_day
    asset.save(update_fields=["status", "decommissioned_on"])
    return asset


def asset_total_cost(*, asset_id: str) -> Decimal:
    """Maintenance costs stay reconcilable with finance (spec G14)."""
    total = Decimal("0.00")
    for operation in MaintenanceOperation.objects.filter(asset_id=asset_id):
        total += operation.cost
    return total
