from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.billing.services import invoice_remaining

from .models import Payment, PaymentAllocation


@transaction.atomic
def register_payment(
    *,
    organization_id: str,
    amount: Decimal,
    method: str,
    idempotency_key: str,
    party_id: str | None = None,
    currency: str = "EUR",
    provider_reference: str = "",
) -> Payment:
    """Webhook-safe: the same external event received twice creates a single payment."""
    payment, _ = Payment.objects.get_or_create(
        organization_id=organization_id,
        idempotency_key=idempotency_key,
        defaults={
            "party_id": party_id,
            "amount": amount,
            "currency": currency,
            "method": method,
            "provider_reference": provider_reference,
        },
    )
    return payment


def payment_unallocated(payment: Payment) -> Decimal:
    allocated = payment.allocations.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return payment.amount - allocated


@transaction.atomic
def allocate_payment(*, payment_id: str, invoice_id: str, amount: Decimal) -> PaymentAllocation:
    """An allocation can exceed neither the available payment nor the invoice remainder (spec 11.2)."""
    payment = Payment.objects.select_for_update().get(id=payment_id)
    invoice = Invoice.objects.select_for_update().get(id=invoice_id)

    if invoice.organization_id != payment.organization_id:
        raise ValueError("Payment and invoice belong to different organizations.")
    if invoice.currency != payment.currency:
        raise ValueError("Currency mismatch between payment and invoice.")
    if amount <= 0:
        raise ValueError("Allocation amount must be positive.")

    available = payment_unallocated(payment)
    if amount > available:
        raise ValueError(f"Allocation {amount} exceeds unallocated payment amount {available}.")

    remaining = invoice_remaining(invoice)
    if amount > remaining:
        raise ValueError(f"Allocation {amount} exceeds invoice remaining due {remaining}.")

    return PaymentAllocation.objects.create(payment=payment, invoice=invoice, amount=amount)
