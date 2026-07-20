from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from modular_brix.foundation.sequences.services import allocate_number

from .models import LetteringGroup, OpenItem, Settlement


@transaction.atomic
def create_open_item(
    *,
    organization_id: str,
    party_id: str,
    direction: str,
    source_kind: str,
    source_id: str,
    amount: Decimal,
) -> OpenItem:
    if direction not in ("debit", "credit"):
        raise ValueError("An open item direction is debit or credit.")
    if amount <= 0:
        raise ValueError("An open item amount must be positive.")
    return OpenItem.objects.create(
        organization_id=organization_id,
        party_id=party_id,
        direction=direction,
        source_kind=source_kind,
        source_id=source_id,
        amount=amount,
    )


def settled_amount(item: OpenItem) -> Decimal:
    total = item.settlements.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


def remaining_amount(item: OpenItem) -> Decimal:
    return item.amount - settled_amount(item)


@transaction.atomic
def letter_items(*, organization_id: str, party_id: str, allocations: dict[str, Decimal]) -> LetteringGroup:
    """Total or partial lettering: each allocation is capped by the item remainder, and the
    debit side of the group always equals its credit side (spec C09)."""
    if not allocations:
        raise ValueError("Lettering requires at least one allocation.")
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    items: list[tuple[OpenItem, Decimal]] = []
    for item_id, amount in allocations.items():
        item = OpenItem.objects.select_for_update().get(id=item_id)
        if str(item.organization_id) != str(organization_id) or str(item.party_id) != str(party_id):
            raise ValueError("Lettering never crosses organizations or parties.")
        if amount <= 0:
            raise ValueError("A lettering amount must be positive.")
        remainder = remaining_amount(item)
        if amount > remainder:
            raise ValueError(f"Lettering {amount} exceeds the remainder {remainder} of an item.")
        items.append((item, amount))
        if item.direction == "debit":
            debit_total += amount
        else:
            credit_total += amount
    if debit_total != credit_total:
        raise ValueError(f"A lettering group must balance (debit {debit_total}, credit {credit_total}).")
    number = allocate_number(organization_id=str(organization_id), code="lettering", period="all")
    group = LetteringGroup.objects.create(
        organization_id=organization_id, party_id=party_id, code=f"L{number:06d}"
    )
    for item, amount in items:
        Settlement.objects.create(group=group, open_item=item, amount=amount)
    return group


@transaction.atomic
def unletter_group(*, group_id: str) -> None:
    """Controlled unlettering restores every remainder in one transaction."""
    group = LetteringGroup.objects.select_for_update().get(id=group_id)
    group.settlements.all().delete()
    group.delete()


def party_balance(*, organization_id: str, party_id: str) -> Decimal:
    """Sum of unsettled remainders, signed debit-positive: the subledger position."""
    balance = Decimal("0.00")
    for item in OpenItem.objects.filter(organization_id=organization_id, party_id=party_id):
        remainder = remaining_amount(item)
        balance += remainder if item.direction == "debit" else -remainder
    return balance
