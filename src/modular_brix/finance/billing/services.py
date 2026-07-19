from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modular_brix.common.money import compute_totals
from modular_brix.foundation.sequences.services import allocate_number, format_reference
from modular_brix.management.sales.models import SalesOrder

from .models import CreditNote, Invoice, InvoiceLine


@transaction.atomic
def create_invoice_from_order(*, order_id: str) -> Invoice:
    """Idempotent conversion: the same order always yields the same single invoice."""
    order = SalesOrder.objects.select_for_update().select_related("party", "organization").get(id=order_id)
    existing = Invoice.objects.filter(sales_order=order).first()
    if existing is not None:
        return existing

    invoice = Invoice.objects.create(
        organization_id=order.organization_id,
        party_id=order.party_id,
        sales_order=order,
        currency=order.currency,
    )
    for line in order.lines.order_by("position"):
        InvoiceLine.objects.create(
            invoice=invoice,
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
        )
    return invoice


@transaction.atomic
def issue_invoice(*, invoice_id: str, payment_term_days: int = 30) -> Invoice:
    """Issuance is irreversible: chronological number, frozen snapshots and totals."""
    invoice = Invoice.objects.select_for_update().select_related("organization", "party").get(id=invoice_id)
    if invoice.status != "draft":
        raise ValueError("Only a draft invoice can be issued.")
    if not invoice.lines.exists():
        raise ValueError("An empty invoice cannot be issued.")

    today = timezone.now().date()
    year = str(today.year)
    number = allocate_number(organization_id=str(invoice.organization_id), code="invoice", period=year)
    totals = compute_totals(invoice.lines.all())

    invoice.number = format_reference(prefix="INV", period=year, number=number)
    invoice.status = "issued"
    invoice.issue_date = today
    invoice.due_date = today + timedelta(days=payment_term_days)
    invoice.seller_name = invoice.organization.legal_name
    invoice.buyer_name = invoice.party.display_name
    invoice.total_excl_tax = totals.excl_tax
    invoice.total_tax = totals.tax
    invoice.total_incl_tax = totals.incl_tax
    invoice.save()
    return invoice


def credited_amount(invoice: Invoice) -> Decimal:
    return invoice.credit_notes.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def allocated_amount(invoice: Invoice) -> Decimal:
    total = invoice.allocations.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


def invoice_remaining(invoice: Invoice) -> Decimal:
    """Remaining due = issued total - credit notes - payment allocations."""
    if invoice.status != "issued":
        raise ValueError("Balance is only defined for an issued invoice.")
    return invoice.total_incl_tax - credited_amount(invoice) - allocated_amount(invoice)


@transaction.atomic
def create_credit_note(*, invoice_id: str, amount: Decimal, reason: str) -> CreditNote:
    """A credit note can never exceed what remains creditable on the invoice (spec 11.2)."""
    invoice = Invoice.objects.select_for_update().get(id=invoice_id)
    if invoice.status != "issued":
        raise ValueError("Credit notes only apply to issued invoices.")
    if amount <= 0:
        raise ValueError("Credit note amount must be positive.")
    if not reason.strip():
        raise ValueError("A credit note reason is required.")

    creditable = invoice.total_incl_tax - credited_amount(invoice)
    if amount > creditable:
        raise ValueError(f"Credit note amount {amount} exceeds creditable remainder {creditable}.")

    year = str(timezone.now().year)
    number = allocate_number(organization_id=str(invoice.organization_id), code="credit-note", period=year)
    return CreditNote.objects.create(
        invoice=invoice,
        number=format_reference(prefix="CN", period=year, number=number),
        amount=amount,
        reason=reason.strip(),
    )
