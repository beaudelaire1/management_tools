from decimal import Decimal

from django.db import transaction

from modular_brix.common.money import round_money

from .models import Forecast, ForecastLine, ForecastVersion


def _project_amounts(*, base_amount: Decimal, growth_percent: Decimal, periods: list[str]) -> dict[str, Decimal]:
    """Deterministic projection: same assumptions always produce the same lines."""
    amounts: dict[str, Decimal] = {}
    current = Decimal(base_amount)
    factor = Decimal("1") + Decimal(growth_percent) / Decimal("100")
    for period in periods:
        amounts[period] = round_money(current)
        current *= factor
    return amounts


@transaction.atomic
def build_forecast_version(
    *,
    forecast_id: str,
    base_amount: Decimal,
    growth_percent: Decimal,
    periods: list[str],
) -> ForecastVersion:
    """Assumptions are stored with the version; recomputation is deterministic (spec P05).

    This service never writes to source domain tables.
    """
    forecast = Forecast.objects.select_for_update().get(id=forecast_id)
    latest = forecast.versions.order_by("-version").first()
    next_version = (latest.version + 1) if latest else 1
    version = ForecastVersion.objects.create(
        forecast=forecast,
        version=next_version,
        assumptions={
            "base_amount": str(base_amount),
            "growth_percent": str(growth_percent),
            "periods": periods,
        },
    )
    for period, amount in _project_amounts(
        base_amount=base_amount, growth_percent=growth_percent, periods=periods
    ).items():
        ForecastLine.objects.create(version=version, period=period, amount=amount)
    return version


def compare_scenarios(
    *,
    base_amount: Decimal,
    periods: list[str],
    scenarios: dict[str, Decimal],
) -> dict[str, Decimal]:
    """P06 baseline: side-effect-free comparison of growth scenarios; nothing is booked."""
    results: dict[str, Decimal] = {}
    for name, growth_percent in scenarios.items():
        amounts = _project_amounts(base_amount=base_amount, growth_percent=growth_percent, periods=periods)
        results[name] = sum(amounts.values(), Decimal("0.00"))
    return results
