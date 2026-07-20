from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction

from modular_brix.management.purchasing.models import PurchaseOrder
from modular_brix.management.purchasing.services import received_quantity

from .models import PaymentProposal, PaymentProposalLine, SupplierInvoice


@transaction.atomic
def register_supplier_invoice(
    *,
    organization_id: str,
    supplier_id: str,
    reference: str,
    invoice_date: date,
    amount_excl_tax: Decimal,
    tax_amount: Decimal,
    purchase_order_id: str | None = None,
    due_date: date | None = None,
) -> SupplierInvoice:
    if amount_excl_tax + tax_amount <= 0:
        raise ValueError("A supplier invoice total must be positive.")
    if purchase_order_id is not None:
        order = PurchaseOrder.objects.get(id=purchase_order_id)
        if str(order.organization_id) != str(organization_id) or str(order.supplier_id) != str(supplier_id):
            raise ValueError("A matched purchase order must share the invoice organization and supplier.")
    try:
        return SupplierInvoice.objects.create(
            organization_id=organization_id,
            supplier_id=supplier_id,
            reference=reference.strip(),
            invoice_date=invoice_date,
            due_date=due_date,
            amount_excl_tax=amount_excl_tax,
            tax_amount=tax_amount,
            amount_incl_tax=amount_excl_tax + tax_amount,
            purchase_order_id=purchase_order_id,
        )
    except IntegrityError as exc:
        raise ValueError("This supplier invoice is already registered (duplicate reference and date).") from exc


@transaction.atomic
def three_way_match(*, invoice_id: str) -> SupplierInvoice:
    """Order/receipt/invoice comparison: any gap blocks payment until resolved (spec C05)."""
    invoice = (
        SupplierInvoice.objects.select_for_update(of=("self",))
        .select_related("purchase_order")
        .get(id=invoice_id)
    )
    if invoice.purchase_order is None:
        raise ValueError("Three-way match requires a linked purchase order.")
    discrepancies: list[str] = []
    ordered_total = Decimal("0.00")
    for line in invoice.purchase_order.lines.all():
        ordered_total += (line.quantity * line.unit_price).quantize(Decimal("0.01"))
        if received_quantity(line) < line.quantity:
            discrepancies.append(f"line {line.position} not fully received")
    if ordered_total != invoice.amount_excl_tax:
        discrepancies.append(f"invoice {invoice.amount_excl_tax} differs from order {ordered_total}")
    if discrepancies:
        invoice.status = "blocked"
        invoice.block_reason = "; ".join(discrepancies)[:255]
    else:
        invoice.status = "validated"
        invoice.block_reason = ""
    invoice.save(update_fields=["status", "block_reason"])
    return invoice


@transaction.atomic
def validate_invoice(*, invoice_id: str) -> SupplierInvoice:
    invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)
    if invoice.status not in ("received", "blocked"):
        raise ValueError("Only a received or unblocked invoice can be validated.")
    invoice.status = "validated"
    invoice.block_reason = ""
    invoice.save(update_fields=["status", "block_reason"])
    return invoice


@transaction.atomic
def propose_payments(*, organization_id: str) -> PaymentProposal:
    """Only validated, unblocked and unpaid debts enter a payment proposal (spec C05)."""
    proposal = PaymentProposal.objects.create(organization_id=organization_id)
    payable = SupplierInvoice.objects.filter(organization_id=organization_id, status="validated").order_by(
        "due_date", "invoice_date"
    )
    for invoice in payable:
        PaymentProposalLine.objects.create(proposal=proposal, invoice=invoice, amount=invoice.amount_incl_tax)
    return proposal


@transaction.atomic
def mark_paid(*, invoice_id: str) -> SupplierInvoice:
    invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)
    if invoice.status != "validated":
        raise ValueError("Only a validated supplier invoice can be paid.")
    invoice.status = "paid"
    invoice.save(update_fields=["status"])
    return invoice
