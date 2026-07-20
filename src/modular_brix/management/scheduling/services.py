from datetime import datetime

from django.db import transaction

from .models import Absence, Booking, Resource


def _overlapping_bookings(resource: Resource, starts_at: datetime, ends_at: datetime):
    return Booking.objects.filter(
        resource=resource, status="confirmed", starts_at__lt=ends_at, ends_at__gt=starts_at
    )


@transaction.atomic
def book_resource(
    *,
    organization_id: str,
    resource_id: str,
    starts_at: datetime,
    ends_at: datetime,
    reference: str = "",
) -> Booking:
    """Conflict detection is transactional: the resource row is locked before checking overlaps."""
    if ends_at <= starts_at:
        raise ValueError("A booking must end after it starts.")
    resource = Resource.objects.select_for_update().get(id=resource_id)
    if str(resource.organization_id) != str(organization_id):
        raise ValueError("A booking resource must belong to the same organization.")
    if _overlapping_bookings(resource, starts_at, ends_at).exists():
        raise ValueError("This slot conflicts with an existing confirmed booking.")
    if Absence.objects.filter(resource=resource, starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ValueError("This slot conflicts with a declared absence.")
    return Booking.objects.create(
        organization_id=organization_id,
        resource=resource,
        starts_at=starts_at,
        ends_at=ends_at,
        reference=reference,
    )


@transaction.atomic
def cancel_booking(*, booking_id: str) -> Booking:
    booking = Booking.objects.select_for_update().get(id=booking_id)
    if booking.status != "confirmed":
        raise ValueError("Only a confirmed booking can be cancelled.")
    booking.status = "cancelled"
    booking.save(update_fields=["status"])
    return booking


def is_available(*, resource_id: str, starts_at: datetime, ends_at: datetime) -> bool:
    resource = Resource.objects.get(id=resource_id)
    if _overlapping_bookings(resource, starts_at, ends_at).exists():
        return False
    return not Absence.objects.filter(
        resource=resource, starts_at__lt=ends_at, ends_at__gt=starts_at
    ).exists()
