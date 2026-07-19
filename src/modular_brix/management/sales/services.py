from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from modular_brix.common.money import compute_totals
from modular_brix.foundation.sequences.services import allocate_number, format_reference
from modular_brix.management.parties.models import Party

from .models import Delivery, DeliveryLine, Quote, QuoteLine, SalesOrder, SalesOrderLine


@transaction.atomic
def create_quote(*, organization_id: str, party_id: str, currency: str = "EUR") -> Quote:
    party = Party.objects.get(id=party_id)
    if str(party.organization_id) != str(organization_id):
        raise ValueError("A quote and its party must belong to the same organization.")
    if not party.is_active or party.merged_into_id is not None:
        raise ValueError("A quote requires an active, non-merged party.")
    year = str(timezone.now().year)
    number = allocate_number(organization_id=organization_id, code="quote", period=year)
    return Quote.objects.create(
        organization_id=organization_id,
        party=party,
        number=format_reference(prefix="Q", period=year, number=number),
        currency=currency,
    )


@transaction.atomic
def add_quote_line(
    *,
    quote_id: str,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    tax_rate: Decimal,
) -> QuoteLine:
    quote = Quote.objects.select_for_update().get(id=quote_id)
    if quote.status != "draft":
        raise ValueError("Only a draft quote can be modified; revise to create a new version.")
    position = quote.lines.count() + 1
    return QuoteLine.objects.create(
        quote=quote,
        position=position,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=tax_rate,
    )


@transaction.atomic
def send_quote(*, quote_id: str) -> Quote:
    """Sending freezes the version: totals are computed once by the central money service."""
    quote = Quote.objects.select_for_update().get(id=quote_id)
    if quote.status != "draft":
        raise ValueError("Only a draft quote can be sent.")
    if not quote.lines.exists():
        raise ValueError("An empty quote cannot be sent.")
    totals = compute_totals(quote.lines.all())
    quote.total_excl_tax = totals.excl_tax
    quote.total_tax = totals.tax
    quote.total_incl_tax = totals.incl_tax
    quote.status = "sent"
    quote.save(update_fields=["total_excl_tax", "total_tax", "total_incl_tax", "status"])
    return quote


@transaction.atomic
def revise_quote(*, quote_id: str) -> Quote:
    """Modification after sending creates a new version; the sent version stays frozen."""
    original = Quote.objects.select_for_update().get(id=quote_id)
    if original.status not in ("sent", "rejected"):
        raise ValueError("Only a sent or rejected quote can be revised.")
    revision = Quote.objects.create(
        organization_id=original.organization_id,
        party_id=original.party_id,
        number=original.number,
        version=original.version + 1,
        previous_version=original,
        currency=original.currency,
    )
    for line in original.lines.order_by("position"):
        QuoteLine.objects.create(
            quote=revision,
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
        )
    return revision


@transaction.atomic
def accept_quote(*, quote_id: str, acceptance_proof: str) -> Quote:
    if not acceptance_proof.strip():
        raise ValueError("Acceptance proof is required.")
    quote = Quote.objects.select_for_update().get(id=quote_id)
    if quote.status != "sent":
        raise ValueError("Only a sent quote can be accepted.")
    quote.status = "accepted"
    quote.accepted_at = timezone.now()
    quote.acceptance_proof = acceptance_proof.strip()
    quote.save(update_fields=["status", "accepted_at", "acceptance_proof"])
    return quote


@transaction.atomic
def convert_quote_to_order(*, quote_id: str) -> SalesOrder:
    """Idempotent conversion: converting the same accepted quote twice returns the same order."""
    quote = Quote.objects.select_for_update().get(id=quote_id)
    if quote.status != "accepted":
        raise ValueError("Only an accepted quote can be converted to an order.")

    existing = SalesOrder.objects.filter(quote=quote).first()
    if existing is not None:
        return existing

    year = str(timezone.now().year)
    number = allocate_number(organization_id=str(quote.organization_id), code="order", period=year)
    order = SalesOrder.objects.create(
        organization_id=quote.organization_id,
        party_id=quote.party_id,
        quote=quote,
        number=format_reference(prefix="SO", period=year, number=number),
        currency=quote.currency,
        total_excl_tax=quote.total_excl_tax,
        total_tax=quote.total_tax,
        total_incl_tax=quote.total_incl_tax,
    )
    for line in quote.lines.order_by("position"):
        SalesOrderLine.objects.create(
            order=order,
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
        )
    return order


@transaction.atomic
def record_delivery(*, order_id: str, items: list[tuple[str, Decimal]]) -> Delivery:
    """Delivered quantity is capped at the ordered quantity (spec G05)."""
    order = SalesOrder.objects.select_for_update().get(id=order_id)
    if order.status != "open":
        raise ValueError("Deliveries can only be recorded on an open order.")

    delivery = Delivery.objects.create(order=order)
    for line_id, quantity in items:
        line = SalesOrderLine.objects.select_for_update().get(id=line_id, order=order)
        remaining = line.quantity - line.delivered_quantity
        if quantity <= 0:
            raise ValueError("Delivered quantity must be positive.")
        if quantity > remaining:
            raise ValueError(
                f"Line {line.position}: delivered quantity {quantity} exceeds remaining {remaining}."
            )
        line.delivered_quantity += quantity
        line.save(update_fields=["delivered_quantity"])
        DeliveryLine.objects.create(delivery=delivery, order_line=line, quantity=quantity)

    if not order.lines.filter(delivered_quantity__lt=F("quantity")).exists():
        order.status = "fulfilled"
        order.save(update_fields=["status"])
    return delivery
