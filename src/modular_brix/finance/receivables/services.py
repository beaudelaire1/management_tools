from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.billing.services import invoice_remaining

from .models import Dispute, Reminder


def _open_invoices(organization_id: str):
    return Invoice.objects.filter(organization_id=organization_id, status="issued")


def aging_buckets(*, organization_id: str, as_of: date) -> dict[str, Decimal]:
    """Reproducible aging balance: same date and data always yield the same buckets."""
    buckets = {
        "current": Decimal("0.00"),
        "1-30": Decimal("0.00"),
        "31-60": Decimal("0.00"),
        "60+": Decimal("0.00"),
    }
    for invoice in _open_invoices(organization_id).order_by("issue_date"):
        remaining = invoice_remaining(invoice)
        if remaining <= 0:
            continue
        overdue_days = (as_of - invoice.due_date).days
        if overdue_days <= 0:
            buckets["current"] += remaining
        elif overdue_days <= 30:
            buckets["1-30"] += remaining
        elif overdue_days <= 60:
            buckets["31-60"] += remaining
        else:
            buckets["60+"] += remaining
    return buckets


@transaction.atomic
def open_dispute(*, invoice_id: str, reason: str) -> Dispute:
    if not reason.strip():
        raise ValueError("A dispute reason is required.")
    return Dispute.objects.create(invoice_id=invoice_id, reason=reason.strip())


@transaction.atomic
def resolve_dispute(*, dispute_id: str) -> Dispute:
    dispute = Dispute.objects.select_for_update().get(id=dispute_id)
    dispute.status = "resolved"
    dispute.resolved_at = timezone.now()
    dispute.save(update_fields=["status", "resolved_at"])
    return dispute


@transaction.atomic
def send_due_reminders(*, organization_id: str, as_of: date) -> list[Reminder]:
    """Reminders never target paid invoices nor invoices under an open dispute (spec C03)."""
    reminders: list[Reminder] = []
    for invoice in _open_invoices(organization_id):
        if invoice.due_date is None or invoice.due_date >= as_of:
            continue
        if invoice_remaining(invoice) <= 0:
            continue  # Paid invoices leave the reminder cycle.
        if invoice.disputes.filter(status="open").exists():
            continue  # Suspended while disputed.
        level = invoice.reminders.count() + 1
        reminders.append(Reminder.objects.create(invoice=invoice, level=level))
    return reminders
