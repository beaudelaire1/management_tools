from datetime import date
from decimal import Decimal

from django.db import models, transaction

from .models import CatalogItem, Price


@transaction.atomic
def set_price(
    *,
    item_id: str,
    amount: Decimal,
    valid_from: date,
    currency: str = "EUR",
    valid_to: date | None = None,
) -> Price:
    return Price.objects.create(
        item_id=item_id,
        amount=amount,
        currency=currency,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def resolve_price(*, item_id: str, on_date: date, currency: str = "EUR") -> Price:
    """Historical price resolution: the applicable price at any past date is reproducible."""
    item = CatalogItem.objects.get(id=item_id)
    if not item.is_active:
        raise ValueError("An archived catalog item cannot be priced.")
    price = (
        Price.objects.filter(item_id=item_id, currency=currency, valid_from__lte=on_date)
        .filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=on_date))
        .order_by("-valid_from")
        .first()
    )
    if price is None:
        raise ValueError(f"No applicable price for item on {on_date.isoformat()}.")
    return price
