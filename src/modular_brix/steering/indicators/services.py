from collections.abc import Callable
from decimal import Decimal

from django.db import transaction

from .models import IndicatorDefinition, IndicatorValue


def _formula_sum(inputs: dict) -> Decimal:
    return sum((Decimal(str(v)) for v in inputs.values()), Decimal("0"))


def _formula_ratio(inputs: dict) -> Decimal:
    denominator = Decimal(str(inputs["denominator"]))
    if denominator == 0:
        raise ValueError("Ratio denominator cannot be zero.")
    return (Decimal(str(inputs["numerator"])) / denominator).quantize(Decimal("0.0001"))


FORMULA_REGISTRY: dict[str, Callable[[dict], Decimal]] = {
    "sum": _formula_sum,
    "ratio": _formula_ratio,
}


@transaction.atomic
def create_indicator(
    *,
    organization_id: str,
    code: str,
    label: str,
    unit: str,
    source: str,
    frequency: str,
    owner: str,
    formula_code: str = "",
) -> IndicatorDefinition:
    """Unit, source, frequency and owner are mandatory; an unknown formula cannot be published."""
    for field_name, value in [("unit", unit), ("source", source), ("frequency", frequency), ("owner", owner)]:
        if not value.strip():
            raise ValueError(f"Indicator field '{field_name}' is required.")
    if formula_code and formula_code not in FORMULA_REGISTRY:
        raise ValueError(f"Unknown formula '{formula_code}': an invalid formula cannot be published.")
    return IndicatorDefinition.objects.create(
        organization_id=organization_id,
        code=code,
        label=label,
        unit=unit,
        source=source,
        frequency=frequency,
        owner=owner,
        formula_code=formula_code,
    )


@transaction.atomic
def record_manual_value(*, definition_id: str, period: str, value: Decimal) -> IndicatorValue:
    indicator_value, _ = IndicatorValue.objects.update_or_create(
        definition_id=definition_id,
        period=period,
        defaults={"value": value, "origin": "manual", "inputs": {}},
    )
    return indicator_value


@transaction.atomic
def compute_indicator_value(*, definition_id: str, period: str, inputs: dict) -> IndicatorValue:
    """Deterministic: the same period and the same inputs always produce the same value."""
    definition = IndicatorDefinition.objects.get(id=definition_id)
    if not definition.formula_code:
        raise ValueError("This indicator has no formula; record a manual value instead.")
    formula = FORMULA_REGISTRY[definition.formula_code]
    result = formula(inputs)
    indicator_value, _ = IndicatorValue.objects.update_or_create(
        definition=definition,
        period=period,
        defaults={"value": result, "origin": "computed", "inputs": inputs},
    )
    return indicator_value


def latest_value(*, definition_id: str) -> IndicatorValue | None:
    return IndicatorValue.objects.filter(definition_id=definition_id).order_by("-period").first()
