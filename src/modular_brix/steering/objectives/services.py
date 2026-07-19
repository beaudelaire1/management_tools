from datetime import date
from decimal import Decimal

from django.db import transaction

from modular_brix.steering.indicators.services import latest_value

from .models import KeyResult, Objective


@transaction.atomic
def create_objective(*, organization_id: str, label: str, owner: str, horizon: date) -> Objective:
    """Owner and horizon are mandatory (spec P03)."""
    if not owner.strip():
        raise ValueError("An objective owner is required.")
    return Objective.objects.create(
        organization_id=organization_id,
        label=label,
        owner=owner,
        horizon=horizon,
    )


@transaction.atomic
def add_key_result(*, objective_id: str, indicator_id: str, target_value: Decimal) -> KeyResult:
    return KeyResult.objects.create(
        objective_id=objective_id,
        indicator_id=indicator_id,
        target_value=target_value,
    )


@transaction.atomic
def activate_objective(*, objective_id: str) -> Objective:
    """An objective must be linked to at least one measurable key result (spec P03)."""
    objective = Objective.objects.select_for_update().get(id=objective_id)
    if not objective.key_results.exists():
        raise ValueError("An objective needs at least one key result linked to an indicator.")
    objective.status = "active"
    objective.save(update_fields=["status"])
    return objective


def objective_progress(*, objective_id: str) -> Decimal:
    """Average of capped key-result completion ratios, in percent."""
    objective = Objective.objects.get(id=objective_id)
    key_results = list(objective.key_results.all())
    if not key_results:
        return Decimal("0")
    total = Decimal("0")
    for key_result in key_results:
        current = latest_value(definition_id=str(key_result.indicator_id))
        achieved = current.value if current is not None else Decimal("0")
        ratio = min(achieved / key_result.target_value, Decimal("1"))
        total += ratio
    return (total / len(key_results) * 100).quantize(Decimal("0.01"))


def is_objective_late(*, objective_id: str, as_of: date) -> bool:
    objective = Objective.objects.get(id=objective_id)
    return objective.horizon < as_of and objective_progress(objective_id=objective_id) < Decimal("100")
