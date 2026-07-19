from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Budget, BudgetActual, BudgetLine, BudgetVersion


@transaction.atomic
def create_budget(*, organization_id: str, label: str, period_start: date, period_end: date) -> Budget:
    if period_end <= period_start:
        raise ValueError("Budget period end must be after its start.")
    budget = Budget.objects.create(
        organization_id=organization_id,
        label=label,
        period_start=period_start,
        period_end=period_end,
    )
    BudgetVersion.objects.create(budget=budget, version=1)
    return budget


@transaction.atomic
def set_budget_line(*, version_id: str, axis: str, amount: Decimal) -> BudgetLine:
    version = BudgetVersion.objects.select_for_update().get(id=version_id)
    if version.status != "draft":
        raise ValueError("An approved budget version is frozen; create a revision.")
    line, _ = BudgetLine.objects.update_or_create(
        version=version,
        axis=axis,
        defaults={"amount": amount},
    )
    return line


@transaction.atomic
def approve_version(*, version_id: str) -> BudgetVersion:
    version = BudgetVersion.objects.select_for_update().get(id=version_id)
    if version.status != "draft":
        raise ValueError("Only a draft version can be approved.")
    if not version.lines.exists():
        raise ValueError("An empty budget version cannot be approved.")
    version.status = "approved"
    version.approved_at = timezone.now()
    version.save(update_fields=["status", "approved_at"])
    return version


@transaction.atomic
def create_revision(*, budget_id: str) -> BudgetVersion:
    """Explicit revision: a new draft version copying the latest one (spec P04)."""
    budget = Budget.objects.select_for_update().get(id=budget_id)
    latest = budget.versions.order_by("-version").first()
    revision = BudgetVersion.objects.create(budget=budget, version=latest.version + 1)
    for line in latest.lines.all():
        BudgetLine.objects.create(version=revision, axis=line.axis, amount=line.amount)
    return revision


@transaction.atomic
def record_actual(*, budget_id: str, axis: str, amount: Decimal) -> BudgetActual:
    return BudgetActual.objects.create(budget_id=budget_id, axis=axis, amount=amount)


def budget_availability(*, budget_id: str) -> dict[str, dict[str, Decimal]]:
    """Per-axis budgeted/consumed/available from the approved version; overspend visible."""
    budget = Budget.objects.get(id=budget_id)
    approved = budget.versions.filter(status="approved").order_by("-version").first()
    if approved is None:
        raise ValueError("No approved budget version.")
    result: dict[str, dict[str, Decimal]] = {}
    for line in approved.lines.all():
        consumed = (
            budget.actuals.filter(axis=line.axis).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        result[line.axis] = {
            "budgeted": line.amount,
            "consumed": consumed,
            "available": line.amount - consumed,
        }
    return result


def overspent_axes(*, budget_id: str) -> list[str]:
    return [
        axis
        for axis, amounts in budget_availability(budget_id=budget_id).items()
        if amounts["available"] < 0
    ]
