from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modular_brix.management.scheduling.models import Absence, Booking, Resource

from .models import UtilizationSnapshot


def _week_bounds(week_start: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = datetime.combine(week_start, time.min, tzinfo=tz)
    return start, start + timedelta(days=7)


def _clipped_hours(starts_at: datetime, ends_at: datetime, window_start: datetime, window_end: datetime) -> Decimal:
    start = max(starts_at, window_start)
    end = min(ends_at, window_end)
    if end <= start:
        return Decimal("0")
    return Decimal((end - start).total_seconds()) / Decimal(3600)


@transaction.atomic
def compute_utilization(*, resource_id: str, week_start: date) -> UtilizationSnapshot:
    """Bookings are the single workload source, so no assignment is ever counted twice;
    absences reduce the available capacity for the week (spec P10)."""
    if week_start.weekday() != 0:
        raise ValueError("A utilization week must start on a Monday.")
    resource = Resource.objects.get(id=resource_id)
    window_start, window_end = _week_bounds(week_start)
    planned = Decimal("0")
    for booking in Booking.objects.filter(
        resource=resource, status="confirmed", starts_at__lt=window_end, ends_at__gt=window_start
    ):
        planned += _clipped_hours(booking.starts_at, booking.ends_at, window_start, window_end)
    absent = Decimal("0")
    for absence in Absence.objects.filter(
        resource=resource, starts_at__lt=window_end, ends_at__gt=window_start
    ):
        absent += _clipped_hours(absence.starts_at, absence.ends_at, window_start, window_end)
    available = max(Decimal(resource.weekly_capacity_hours) - absent, Decimal("0"))
    snapshot, _ = UtilizationSnapshot.objects.update_or_create(
        resource=resource,
        week_start=week_start,
        defaults={
            "organization_id": resource.organization_id,
            "available_hours": available.quantize(Decimal("0.01")),
            "planned_hours": planned.quantize(Decimal("0.01")),
        },
    )
    return snapshot


def overloaded_resources(*, organization_id: str, week_start: date) -> list[UtilizationSnapshot]:
    """Overload is visible, never silently absorbed (spec P10)."""
    return [
        snapshot
        for snapshot in UtilizationSnapshot.objects.filter(
            organization_id=organization_id, week_start=week_start
        ).select_related("resource")
        if snapshot.planned_hours > snapshot.available_hours
    ]
