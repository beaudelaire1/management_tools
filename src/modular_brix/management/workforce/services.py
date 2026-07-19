from datetime import date

from django.db import transaction
from django.utils import timezone

from modular_brix.foundation.audit.services import record_audit_event

from .models import Certification, Employee, EmployeeAssignment, LeaveRequest, Position, SensitiveRecord


@transaction.atomic
def assign_position(*, employee_id: str, position_id: str, starts_on: date) -> EmployeeAssignment:
    """An expired required certification blocks the assignment (spec G15)."""
    employee = Employee.objects.get(id=employee_id)
    position = Position.objects.get(id=position_id)
    if str(employee.organization_id) != str(position.organization_id):
        raise ValueError("An assignment must stay inside the same organization.")
    if position.required_certification:
        certification = (
            Certification.objects.filter(employee=employee, name=position.required_certification)
            .order_by("-expires_on")
            .first()
        )
        if certification is None:
            raise ValueError(f"Certification {position.required_certification} is required for this position.")
        if certification.expires_on is not None and certification.expires_on < starts_on:
            raise ValueError(f"Certification {position.required_certification} is expired.")
    return EmployeeAssignment.objects.create(employee=employee, position=position, starts_on=starts_on)


@transaction.atomic
def approve_leave(*, leave_id: str, approver_membership_id: str) -> LeaveRequest:
    """Nobody approves their own leave request."""
    leave = LeaveRequest.objects.select_for_update().select_related("employee").get(id=leave_id)
    if leave.status != "pending":
        raise ValueError("Only a pending leave request can be approved.")
    if leave.employee.membership_id is not None and str(leave.employee.membership_id) == str(
        approver_membership_id
    ):
        raise ValueError("A leave request cannot be approved by its own requester.")
    leave.status = "approved"
    leave.approved_by_id = approver_membership_id
    leave.save(update_fields=["status", "approved_by"])
    return leave


def read_sensitive_record(*, employee_id: str, actor_user_id: int | None) -> dict:
    """Every consultation of a sensitive HR record leaves an audit event (spec G15)."""
    record = SensitiveRecord.objects.select_related("employee").get(employee_id=employee_id)
    record_audit_event(
        organization_id=str(record.employee.organization_id),
        actor_user_id=actor_user_id,
        event_type="workforce.sensitive_record.read",
        object_type="workforce.SensitiveRecord",
        object_id=str(record.id),
        outcome="success",
        context={"employee_id": str(employee_id)},
    )
    return record.payload


def expired_certifications(*, organization_id: str) -> list[Certification]:
    today = timezone.now().date()
    return list(
        Certification.objects.filter(
            employee__organization_id=organization_id, expires_on__isnull=False, expires_on__lt=today
        ).select_related("employee")
    )
