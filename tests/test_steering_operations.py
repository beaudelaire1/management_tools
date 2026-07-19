"""Lot 5 steering bricks (P10-P12): acceptance-criteria tests."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.management.scheduling.models import Absence, Resource
from modular_brix.management.scheduling.services import book_resource
from modular_brix.steering.capacity.services import compute_utilization, overloaded_resources
from modular_brix.steering.quality.models import CorrectiveAction, NonConformity
from modular_brix.steering.quality.services import (
    close_non_conformity,
    complete_action,
    open_non_conformity,
    overdue_actions,
    reopen_non_conformity,
    resolution_days,
)
from modular_brix.steering.risks.models import Control, Incident, Risk
from modular_brix.steering.risks.services import (
    assess_risk,
    critical_risks,
    overdue_controls,
    record_control_execution,
)


def _org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"steer-{suffix}",
        legal_name=f"Steer {suffix}",
        legal_identifier=f"STEER-{suffix}",
        country_code="FR",
    )


@pytest.mark.django_db
def test_capacity_utilization_counts_bookings_once_and_flags_overload() -> None:
    org = _org("p10")
    resource = Resource.objects.create(
        organization=org, kind="person", name="Technicien", weekly_capacity_hours=Decimal("10")
    )
    monday = date(2026, 8, 3)
    start = timezone.make_aware(datetime(2026, 8, 3, 9))
    book_resource(
        organization_id=str(org.id),
        resource_id=str(resource.id),
        starts_at=start,
        ends_at=start + timedelta(hours=6),
    )
    book_resource(
        organization_id=str(org.id),
        resource_id=str(resource.id),
        starts_at=start + timedelta(days=1),
        ends_at=start + timedelta(days=1, hours=3),
    )
    Absence.objects.create(
        resource=resource,
        starts_at=start + timedelta(days=2),
        ends_at=start + timedelta(days=2, hours=4),
        reason="congé",
    )

    snapshot = compute_utilization(resource_id=str(resource.id), week_start=monday)
    assert snapshot.planned_hours == Decimal("9.00")  # no double counting
    assert snapshot.available_hours == Decimal("6.00")  # capacity minus absence
    assert [entry.resource_id for entry in overloaded_resources(organization_id=str(org.id), week_start=monday)] == [
        resource.id
    ]

    with pytest.raises(ValueError, match="Monday"):
        compute_utilization(resource_id=str(resource.id), week_start=date(2026, 8, 4))


@pytest.mark.django_db
def test_risk_assessments_keep_history_and_overdue_controls_flagged() -> None:
    org = _org("p11")
    risk = Risk.objects.create(organization=org, title="Perte de données", owner_name="DSI")

    assess_risk(
        risk_id=str(risk.id),
        assessed_on=date(2026, 5, 1),
        impact=4,
        probability=3,
        residual_impact=2,
        residual_probability=2,
    )
    assess_risk(
        risk_id=str(risk.id),
        assessed_on=date(2026, 7, 1),
        impact=5,
        probability=4,
        residual_impact=3,
        residual_probability=2,
    )
    assert risk.assessments.count() == 2  # rating history preserved
    with pytest.raises(ValueError, match="residual"):
        assess_risk(
            risk_id=str(risk.id),
            assessed_on=date(2026, 7, 2),
            impact=2,
            probability=2,
            residual_impact=5,
            residual_probability=5,
        )
    assert critical_risks(organization_id=str(org.id)) == [risk]  # 5x4 >= 16 escalates

    control = Control.objects.create(risk=risk, name="Test de restauration", frequency_days=30)
    assert control in overdue_controls(organization_id=str(org.id), on_day=date(2026, 9, 1))
    with pytest.raises(ValueError, match="evidence"):
        record_control_execution(control_id=str(control.id), executed_on=date(2026, 8, 30), evidence=" ")
    record_control_execution(
        control_id=str(control.id), executed_on=date(2026, 8, 30), evidence="PV de restauration"
    )
    assert control not in overdue_controls(organization_id=str(org.id), on_day=date(2026, 9, 1))

    incident = Incident.objects.create(
        organization=org, risk=risk, happened_at=timezone.now(), description="Corruption sauvegarde"
    )
    assert incident.risk_id == risk.id  # incident linked to the risk


@pytest.mark.django_db
def test_non_conformity_closure_requires_evidence_and_reopening_is_traced() -> None:
    org = _org("p12")
    nc = open_non_conformity(
        organization_id=str(org.id), description="Livraison non conforme", severity="major"
    )
    action = CorrectiveAction.objects.create(
        non_conformity=nc, description="Reprendre la pièce", due_date=date(2026, 7, 1)
    )
    assert action in overdue_actions(organization_id=str(org.id))

    with pytest.raises(ValueError, match="closure is blocked"):
        close_non_conformity(non_conformity_id=str(nc.id), root_cause="Outillage usé")
    with pytest.raises(ValueError, match="evidence"):
        complete_action(action_id=str(action.id), evidence="  ")
    complete_action(action_id=str(action.id), evidence="Photo de la pièce reprise")

    with pytest.raises(ValueError, match="root cause"):
        close_non_conformity(non_conformity_id=str(nc.id))
    closed = close_non_conformity(non_conformity_id=str(nc.id), root_cause="Outillage usé")
    assert resolution_days(closed) is not None

    reopened = reopen_non_conformity(non_conformity_id=str(nc.id))
    assert reopened.reopened_count == 1
    assert NonConformity.objects.get(id=nc.id).status == "open"


@pytest.mark.django_db
def test_invalid_severity_rejected() -> None:
    org = _org("p12b")
    with pytest.raises(ValueError, match="Severity"):
        open_non_conformity(organization_id=str(org.id), description="X", severity="urgent")
