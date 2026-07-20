from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .models import Control, ControlExecution, Risk, RiskAssessment

CRITICAL_SCORE = 16  # impact x probability at or above this escalates


@transaction.atomic
def assess_risk(
    *,
    risk_id: str,
    assessed_on: date,
    impact: int,
    probability: int,
    residual_impact: int,
    residual_probability: int,
) -> RiskAssessment:
    for value in (impact, probability, residual_impact, residual_probability):
        if not 1 <= value <= 5:
            raise ValueError("Risk ratings use a 1 to 5 scale.")
    if residual_impact * residual_probability > impact * probability:
        raise ValueError("A residual rating cannot exceed the gross rating.")
    risk = Risk.objects.get(id=risk_id)
    if risk.status != "open":
        raise ValueError("Only an open risk can be assessed.")
    return RiskAssessment.objects.create(
        risk=risk,
        assessed_on=assessed_on,
        impact=impact,
        probability=probability,
        residual_impact=residual_impact,
        residual_probability=residual_probability,
    )


def is_critical(risk: Risk) -> bool:
    latest = risk.assessments.order_by("-assessed_on").first()
    return latest is not None and latest.impact * latest.probability >= CRITICAL_SCORE


@transaction.atomic
def record_control_execution(*, control_id: str, executed_on: date, evidence: str) -> ControlExecution:
    """A control execution without evidence proves nothing (spec P11)."""
    if not evidence.strip():
        raise ValueError("A control execution requires evidence.")
    control = Control.objects.select_for_update().get(id=control_id)
    execution = ControlExecution.objects.create(
        control=control, executed_on=executed_on, evidence=evidence.strip()
    )
    if control.last_executed_on is None or executed_on > control.last_executed_on:
        control.last_executed_on = executed_on
        control.save(update_fields=["last_executed_on"])
    return execution


def overdue_controls(*, organization_id: str, on_day: date | None = None) -> list[Control]:
    today = on_day or timezone.now().date()
    overdue = []
    for control in Control.objects.filter(risk__organization_id=organization_id, risk__status="open"):
        reference = control.last_executed_on or control.risk.created_at.date()
        if today > reference + timedelta(days=control.frequency_days):
            overdue.append(control)
    return overdue


def critical_risks(*, organization_id: str) -> list[Risk]:
    return [
        risk
        for risk in Risk.objects.filter(organization_id=organization_id, status="open")
        if is_critical(risk)
    ]
