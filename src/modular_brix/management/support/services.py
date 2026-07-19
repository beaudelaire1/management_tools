from datetime import timedelta

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import SLAPolicy, Ticket, TicketMessage


@transaction.atomic
def open_ticket(*, organization_id: str, party_id: str, subject: str, priority: str = "normal") -> Ticket:
    """The SLA clock starts at opening, from the policy configured for the priority."""
    policy = SLAPolicy.objects.filter(organization_id=organization_id, priority=priority).first()
    ticket = Ticket.objects.create(
        organization_id=organization_id, party_id=party_id, subject=subject, priority=priority
    )
    if policy is not None:
        ticket.sla_due_at = ticket.opened_at + timedelta(hours=policy.resolution_hours)
        ticket.save(update_fields=["sla_due_at"])
    return ticket


@transaction.atomic
def add_message(*, ticket_id: str, author_name: str, body: str, is_private: bool = False) -> TicketMessage:
    ticket = Ticket.objects.get(id=ticket_id)
    if ticket.status == "closed":
        raise ValueError("A closed ticket cannot receive messages.")
    return TicketMessage.objects.create(
        ticket=ticket, author_name=author_name, body=body, is_private=is_private
    )


def customer_visible_messages(*, ticket_id: str) -> QuerySet[TicketMessage]:
    """Private notes are structurally separated from customer-facing replies (spec G13)."""
    return TicketMessage.objects.filter(ticket_id=ticket_id, is_private=False).order_by("sent_at")


@transaction.atomic
def resolve_ticket(*, ticket_id: str) -> Ticket:
    ticket = Ticket.objects.select_for_update().get(id=ticket_id)
    if ticket.status != "open":
        raise ValueError("Only an open ticket can be resolved.")
    ticket.status = "resolved"
    ticket.resolved_at = timezone.now()
    ticket.save(update_fields=["status", "resolved_at"])
    return ticket


@transaction.atomic
def reopen_ticket(*, ticket_id: str) -> Ticket:
    """Reopening is allowed and always traced by an incremented counter."""
    ticket = Ticket.objects.select_for_update().get(id=ticket_id)
    if ticket.status != "resolved":
        raise ValueError("Only a resolved ticket can be reopened.")
    ticket.status = "open"
    ticket.resolved_at = None
    ticket.reopened_count += 1
    ticket.save(update_fields=["status", "resolved_at", "reopened_count"])
    return ticket


def overdue_tickets(*, organization_id: str) -> QuerySet[Ticket]:
    return Ticket.objects.filter(
        organization_id=organization_id, status="open", sla_due_at__lt=timezone.now()
    )
