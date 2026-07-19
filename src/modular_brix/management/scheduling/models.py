import uuid

from django.db import models


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="schedulable_resources"
    )
    kind = models.CharField(max_length=16)  # person | room | equipment
    name = models.CharField(max_length=255)
    weekly_capacity_hours = models.DecimalField(max_digits=6, decimal_places=2, default=35)
    is_active = models.BooleanField(default=True)


class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="bookings"
    )
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="bookings")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, default="confirmed")  # confirmed | cancelled
    reference = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="ck_booking_positive_duration"
            )
        ]


class Absence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="absences")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=128, blank=True)
