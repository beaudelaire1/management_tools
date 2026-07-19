import uuid

from django.db import models


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="employees"
    )
    membership = models.OneToOneField(
        "foundation_accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="employee",
    )
    full_name = models.CharField(max_length=255)
    hired_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class SensitiveRecord(models.Model):
    """Sensitive HR data is isolated in its own table and only read through the audited service."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.OneToOneField(Employee, on_delete=models.PROTECT, related_name="sensitive_record")
    payload = models.JSONField(default=dict)


class Position(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="positions"
    )
    title = models.CharField(max_length=255)
    required_certification = models.CharField(max_length=128, blank=True)


class EmployeeAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="position_assignments")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="assignments")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)


class Certification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="certifications")
    name = models.CharField(max_length=128)
    expires_on = models.DateField(null=True, blank=True)


class LeaveRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, default="pending")  # pending | approved | rejected
    approved_by = models.ForeignKey(
        "foundation_accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_leaves",
    )
    created_at = models.DateTimeField(auto_now_add=True)
