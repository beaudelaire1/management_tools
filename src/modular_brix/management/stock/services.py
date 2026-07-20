from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import InventoryCount, StockMovement, StockReservation, Warehouse


@transaction.atomic
def record_movement(
    *,
    organization_id: str,
    warehouse_id: str,
    item_id: str,
    quantity: Decimal,
    reason: str,
    reference: str = "",
) -> StockMovement:
    if quantity == 0:
        raise ValueError("A stock movement must have a non-zero quantity.")
    warehouse = Warehouse.objects.get(id=warehouse_id)
    if str(warehouse.organization_id) != str(organization_id):
        raise ValueError("A stock movement warehouse must belong to the same organization.")
    return StockMovement.objects.create(
        organization_id=organization_id,
        warehouse_id=warehouse_id,
        item_id=item_id,
        quantity=quantity,
        reason=reason,
        reference=reference,
    )


def stock_level(*, warehouse_id: str, item_id: str) -> Decimal:
    """Physical stock is always the sum of movements, never a stored counter."""
    total = StockMovement.objects.filter(warehouse_id=warehouse_id, item_id=item_id).aggregate(
        total=Sum("quantity")
    )["total"]
    return total or Decimal("0")


def reserved_quantity(*, warehouse_id: str, item_id: str) -> Decimal:
    total = StockReservation.objects.filter(
        warehouse_id=warehouse_id, item_id=item_id, status="active"
    ).aggregate(total=Sum("quantity"))["total"]
    return total or Decimal("0")


def available_quantity(*, warehouse_id: str, item_id: str) -> Decimal:
    return stock_level(warehouse_id=warehouse_id, item_id=item_id) - reserved_quantity(
        warehouse_id=warehouse_id, item_id=item_id
    )


@transaction.atomic
def reserve_stock(
    *, organization_id: str, warehouse_id: str, item_id: str, quantity: Decimal, reference: str = ""
) -> StockReservation:
    """Reservation is distinct from availability and can never oversell the warehouse."""
    if quantity <= 0:
        raise ValueError("A reservation quantity must be positive.")
    # Serialize concurrent reservations on the same warehouse row.
    Warehouse.objects.select_for_update().get(id=warehouse_id)
    available = available_quantity(warehouse_id=warehouse_id, item_id=item_id)
    if quantity > available:
        raise ValueError(f"Cannot reserve {quantity}; only {available} available.")
    return StockReservation.objects.create(
        organization_id=organization_id,
        warehouse_id=warehouse_id,
        item_id=item_id,
        quantity=quantity,
        reference=reference,
    )


@transaction.atomic
def release_reservation(*, reservation_id: str) -> StockReservation:
    reservation = StockReservation.objects.select_for_update().get(id=reservation_id)
    if reservation.status != "active":
        raise ValueError("Only an active reservation can be released.")
    reservation.status = "released"
    reservation.save(update_fields=["status"])
    return reservation


@transaction.atomic
def record_inventory_count(
    *, warehouse_id: str, item_id: str, counted_quantity: Decimal, justification: str
) -> InventoryCount:
    """An inventory gap is materialized by a justified adjustment movement."""
    if not justification.strip():
        raise ValueError("An inventory count requires a justification.")
    warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)
    current = stock_level(warehouse_id=warehouse_id, item_id=item_id)
    gap = counted_quantity - current
    adjustment = None
    if gap != 0:
        adjustment = StockMovement.objects.create(
            organization_id=warehouse.organization_id,
            warehouse_id=warehouse_id,
            item_id=item_id,
            quantity=gap,
            reason="adjustment",
            reference=justification.strip()[:128],
        )
    return InventoryCount.objects.create(
        warehouse_id=warehouse_id,
        item_id=item_id,
        counted_quantity=counted_quantity,
        justification=justification.strip(),
        adjustment=adjustment,
    )
