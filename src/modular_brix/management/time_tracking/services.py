from datetime import datetime
from decimal import Decimal

from django.db import transaction

from .models import BillingRate, TimeEntry, TimesheetPeriod


def _locked_period_covering(organization_id: str, day) -> TimesheetPeriod | None:
    return TimesheetPeriod.objects.filter(
        organization_id=organization_id, is_locked=True, starts_on__lte=day, ends_on__gte=day
    ).first()


@transaction.atomic
def record_time(
    *,
    organization_id: str,
    worker_membership_id: str,
    activity: str,
    started_at: datetime,
    ended_at: datetime,
    project_id: str | None = None,
    is_billable: bool = True,
) -> TimeEntry:
    """No overlapping entries per worker, and locked periods reject new time (spec G11)."""
    if ended_at <= started_at:
        raise ValueError("A time entry must end after it starts.")
    if _locked_period_covering(organization_id, started_at.date()) is not None:
        raise ValueError("This period is locked; time can no longer be recorded on it.")
    overlap = TimeEntry.objects.filter(
        worker_id=worker_membership_id, started_at__lt=ended_at, ended_at__gt=started_at
    )
    if overlap.exists():
        raise ValueError("This entry overlaps an existing time entry for the same worker.")
    return TimeEntry.objects.create(
        organization_id=organization_id,
        worker_id=worker_membership_id,
        activity=activity,
        started_at=started_at,
        ended_at=ended_at,
        project_id=project_id,
        is_billable=is_billable,
    )


@transaction.atomic
def approve_entry(*, entry_id: str) -> TimeEntry:
    entry = TimeEntry.objects.select_for_update().get(id=entry_id)
    if entry.status != "draft":
        raise ValueError("Only a draft time entry can be approved.")
    entry.status = "approved"
    entry.save(update_fields=["status"])
    return entry


@transaction.atomic
def correct_approved_entry(*, entry_id: str, note: str, started_at: datetime, ended_at: datetime) -> TimeEntry:
    """Correcting approved time is allowed but always leaves a written trace."""
    if not note.strip():
        raise ValueError("Correcting an approved entry requires a note.")
    entry = TimeEntry.objects.select_for_update().get(id=entry_id)
    if entry.status != "approved":
        raise ValueError("Only an approved entry goes through traced correction.")
    entry.started_at = started_at
    entry.ended_at = ended_at
    entry.correction_note = note.strip()
    entry.save(update_fields=["started_at", "ended_at", "correction_note"])
    return entry


def rate_at(*, organization_id: str, activity: str, day) -> BillingRate:
    rate = (
        BillingRate.objects.filter(organization_id=organization_id, activity=activity, valid_from__lte=day)
        .order_by("-valid_from")
        .first()
    )
    if rate is None:
        raise ValueError(f"No billing rate effective for activity {activity} on {day}.")
    return rate


def entry_hours(entry: TimeEntry) -> Decimal:
    seconds = Decimal((entry.ended_at - entry.started_at).total_seconds())
    return (seconds / Decimal(3600)).quantize(Decimal("0.01"))


def value_entry(entry: TimeEntry) -> dict[str, Decimal]:
    """Cost and price are valued separately with the rate effective on the entry date."""
    rate = rate_at(
        organization_id=str(entry.organization_id), activity=entry.activity, day=entry.started_at.date()
    )
    hours = entry_hours(entry)
    return {
        "hours": hours,
        "cost": (hours * rate.hourly_cost).quantize(Decimal("0.01")),
        "price": (hours * rate.hourly_price).quantize(Decimal("0.01")) if entry.is_billable else Decimal("0.00"),
    }
