from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum

from .models import AssetDisposal, DepreciationPeriod, FixedAsset


def linear_plan(asset: FixedAsset) -> list[tuple[str, Decimal]]:
    """Linear monthly plan whose charges sum exactly to the depreciable base: the
    rounding drift is absorbed by the final month (spec C12)."""
    monthly = (asset.acquisition_cost / Decimal(asset.useful_life_months)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    plan: list[tuple[str, Decimal]] = []
    year, month = asset.in_service_on.year, asset.in_service_on.month
    accumulated = Decimal("0.00")
    for index in range(asset.useful_life_months):
        amount = monthly if index < asset.useful_life_months - 1 else asset.acquisition_cost - accumulated
        plan.append((f"{year:04d}-{month:02d}", amount))
        accumulated += amount
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return plan


def depreciated_amount(asset: FixedAsset) -> Decimal:
    total = asset.depreciation_periods.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


@transaction.atomic
def post_depreciation(*, asset_id: str, period: str) -> DepreciationPeriod:
    """Posting follows the plan; a period can never be charged twice."""
    asset = FixedAsset.objects.select_for_update().get(id=asset_id)
    if asset.status != "active":
        raise ValueError("A disposed asset receives no further depreciation.")
    if DepreciationPeriod.objects.filter(asset=asset, period=period).exists():
        raise ValueError(f"Depreciation for {period} is already posted on this asset.")
    plan = dict(linear_plan(asset))
    if period not in plan:
        raise ValueError(f"Period {period} is not part of this asset's depreciation plan.")
    return DepreciationPeriod.objects.create(asset=asset, period=period, amount=plan[period])


def net_book_value(asset: FixedAsset) -> Decimal:
    return asset.acquisition_cost - depreciated_amount(asset)


@transaction.atomic
def dispose_asset(*, asset_id: str, disposed_on: date, proceeds: Decimal = Decimal("0.00")) -> AssetDisposal:
    asset = FixedAsset.objects.select_for_update().get(id=asset_id)
    if asset.status != "active":
        raise ValueError("This asset is already disposed.")
    disposal = AssetDisposal.objects.create(
        asset=asset, disposed_on=disposed_on, proceeds=proceeds, net_book_value=net_book_value(asset)
    )
    asset.status = "disposed"
    asset.save(update_fields=["status"])
    return disposal
