import hashlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modular_brix.management.stock.services import record_movement

from .models import ConsumedItem, CustomerSignature, Intervention


@transaction.atomic
def consume_item(
    *,
    intervention_id: str,
    warehouse_id: str,
    item_id: str,
    quantity: Decimal,
    idempotency_key: str,
) -> ConsumedItem:
    """Stock is decremented exactly once per consumption, even when the call is replayed."""
    intervention = Intervention.objects.select_for_update().get(id=intervention_id)
    if intervention.closed_at is not None:
        raise ValueError("A closed intervention cannot consume items.")
    existing = ConsumedItem.objects.filter(
        intervention=intervention, idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        if str(existing.item_id) != str(item_id) or existing.quantity != quantity:
            raise ValueError("An idempotency key cannot be reused with a different consumption payload.")
        return existing
    movement = record_movement(
        organization_id=str(intervention.work_order.organization_id),
        warehouse_id=warehouse_id,
        item_id=item_id,
        quantity=-quantity,
        reason="consumption",
        reference=f"intervention:{intervention.id}",
    )
    return ConsumedItem.objects.create(
        intervention=intervention,
        item_id=item_id,
        quantity=quantity,
        stock_movement=movement,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def close_intervention(*, intervention_id: str, report: str) -> Intervention:
    """An intervention closes complete: a written report is mandatory (spec G09)."""
    intervention = Intervention.objects.select_for_update().get(id=intervention_id)
    if intervention.closed_at is not None:
        raise ValueError("This intervention is already closed.")
    if not report.strip():
        raise ValueError("An intervention cannot be closed without a report.")
    intervention.report = report.strip()
    intervention.closed_at = timezone.now()
    intervention.save(update_fields=["report", "closed_at"])
    return intervention


@transaction.atomic
def sign_intervention(*, intervention_id: str, signed_by: str) -> CustomerSignature:
    intervention = Intervention.objects.get(id=intervention_id)
    payload = f"{intervention.id}:{signed_by}:{intervention.report}"
    return CustomerSignature.objects.create(
        intervention=intervention,
        signed_by=signed_by,
        payload_hash=hashlib.sha256(payload.encode()).hexdigest(),
    )
