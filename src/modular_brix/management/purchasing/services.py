from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modular_brix.foundation.sequences.services import allocate_number, format_reference

from .models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine, PurchaseRequest


def request_total(request: PurchaseRequest) -> Decimal:
    total = Decimal("0.00")
    for line in request.lines.all():
        total += (line.quantity * line.unit_price).quantize(Decimal("0.01"))
    return total


@transaction.atomic
def submit_request(*, request_id: str) -> PurchaseRequest:
    request = PurchaseRequest.objects.select_for_update().get(id=request_id)
    if request.status != "draft":
        raise ValueError("Only a draft purchase request can be submitted.")
    if not request.lines.exists():
        raise ValueError("An empty purchase request cannot be submitted.")
    request.status = "submitted"
    request.save(update_fields=["status"])
    return request


@transaction.atomic
def approve_request(*, request_id: str, approver_membership_id: str) -> PurchaseRequest:
    """Requester/approver separation: nobody approves their own purchase request."""
    request = PurchaseRequest.objects.select_for_update().get(id=request_id)
    if request.status != "submitted":
        raise ValueError("Only a submitted purchase request can be approved.")
    if str(request.requested_by_id) == str(approver_membership_id):
        raise ValueError("A purchase request cannot be approved by its requester.")
    request.status = "approved"
    request.approved_by_id = approver_membership_id
    request.save(update_fields=["status", "approved_by"])
    return request


@transaction.atomic
def create_order_from_request(*, request_id: str, supplier_id: str) -> PurchaseOrder:
    """Idempotent conversion: an approved request yields exactly one purchase order."""
    request = PurchaseRequest.objects.select_for_update().get(id=request_id)
    if request.status != "approved":
        raise ValueError("Only an approved purchase request can become an order.")
    existing = PurchaseOrder.objects.filter(request=request).first()
    if existing is not None:
        return existing
    year = str(timezone.now().year)
    number = allocate_number(organization_id=str(request.organization_id), code="purchase-order", period=year)
    order = PurchaseOrder.objects.create(
        organization_id=request.organization_id,
        supplier_id=supplier_id,
        request=request,
        number=format_reference(prefix="PO", period=year, number=number),
    )
    for line in request.lines.order_by("position"):
        PurchaseOrderLine.objects.create(
            order=order,
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
    return order


def received_quantity(order_line: PurchaseOrderLine) -> Decimal:
    total = order_line.receipt_lines.aggregate(total=Sum("quantity"))["total"]
    return total or Decimal("0")


@transaction.atomic
def receive_goods(*, order_id: str, quantities: dict[str, Decimal], notes: str = "") -> GoodsReceipt:
    """Partial receipt allowed; the received total can never exceed the ordered quantity."""
    order = PurchaseOrder.objects.select_for_update().get(id=order_id)
    if order.status == "closed":
        raise ValueError("A closed purchase order cannot receive goods.")
    receipt = GoodsReceipt.objects.create(order=order, notes=notes)
    for line_id, quantity in quantities.items():
        line = PurchaseOrderLine.objects.select_for_update().get(id=line_id, order=order)
        if quantity <= 0:
            raise ValueError("A received quantity must be positive.")
        remaining = line.quantity - received_quantity(line)
        if quantity > remaining:
            raise ValueError(f"Received quantity {quantity} exceeds the ordered remainder {remaining}.")
        GoodsReceiptLine.objects.create(receipt=receipt, order_line=line, quantity=quantity)
    fully_received = all(received_quantity(line) >= line.quantity for line in order.lines.all())
    if fully_received:
        order.status = "received"
        order.save(update_fields=["status"])
    return receipt
