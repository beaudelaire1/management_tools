from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import Role
from modular_brix.foundation.permissions.services import assign_role
from modular_brix.steering.budgeting.services import (
    approve_version,
    budget_availability,
    create_budget,
    create_revision,
    overspent_axes,
    record_actual,
    set_budget_line,
)
from modular_brix.steering.dashboards.models import Dashboard
from modular_brix.steering.dashboards.services import add_widget, get_widget_data
from modular_brix.steering.indicators.services import (
    compute_indicator_value,
    create_indicator,
    record_manual_value,
)
from modular_brix.steering.objectives.services import (
    activate_objective,
    add_key_result,
    create_objective,
    is_objective_late,
    objective_progress,
)


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"P-{suffix}",
        country_code="FR",
    )


def _make_membership(org, username: str):
    user = get_user_model().objects.create_user(username=username, password="StrongPass123!")
    return user.memberships.create(organization=org)


def _make_indicator(org, code="revenue", formula_code="sum"):
    return create_indicator(
        organization_id=str(org.id),
        code=code,
        label="Chiffre d'affaires",
        unit="EUR",
        source="finance.billing",
        frequency="monthly",
        owner="Direction",
        formula_code=formula_code,
    )


@pytest.mark.django_db
def test_indicator_requires_metadata_and_valid_formula() -> None:
    org = _make_org("kpi-meta")
    with pytest.raises(ValueError, match="'owner' is required"):
        create_indicator(
            organization_id=str(org.id),
            code="bad",
            label="X",
            unit="EUR",
            source="src",
            frequency="monthly",
            owner="  ",
        )
    with pytest.raises(ValueError, match="invalid formula cannot be published"):
        create_indicator(
            organization_id=str(org.id),
            code="bad2",
            label="X",
            unit="EUR",
            source="src",
            frequency="monthly",
            owner="Dir",
            formula_code="magic",
        )


@pytest.mark.django_db
def test_indicator_computation_is_deterministic_and_origin_tracked() -> None:
    org = _make_org("kpi-det")
    indicator = _make_indicator(org)

    inputs = {"january": "100.50", "february": "200.25"}
    value_1 = compute_indicator_value(definition_id=str(indicator.id), period="2026-Q1", inputs=inputs)
    value_2 = compute_indicator_value(definition_id=str(indicator.id), period="2026-Q1", inputs=inputs)

    assert value_1.value == value_2.value == Decimal("300.75")  # same period + data = same result
    assert value_2.origin == "computed"
    assert value_2.inputs == inputs  # origin of each value inspectable

    manual = record_manual_value(definition_id=str(indicator.id), period="2026-Q2", value=Decimal("42"))
    assert manual.origin == "manual"


@pytest.mark.django_db
def test_widget_catalog_and_permission_enforcement() -> None:
    org = _make_org("dash")
    membership = _make_membership(org, "dash_user")
    indicator = _make_indicator(org)
    record_manual_value(definition_id=str(indicator.id), period="2026-07", value=Decimal("1000"))

    user = membership.user
    dashboard = Dashboard.objects.create(organization=org, owner_user=user, title="Direction")

    with pytest.raises(ValueError, match="authorized catalog"):
        add_widget(dashboard_id=str(dashboard.id), widget_type="iframe")

    widget = add_widget(dashboard_id=str(dashboard.id), widget_type="kpi", indicator_id=str(indicator.id))

    with pytest.raises(PermissionError, match="denied"):
        get_widget_data(widget_id=str(widget.id), membership_id=str(membership.id))  # no bypass

    Role.objects.create(code="reader", label="Reader", can_read=True)
    assign_role(membership_id=str(membership.id), role_code="reader", trusted_system=True)
    data = get_widget_data(widget_id=str(widget.id), membership_id=str(membership.id))
    assert data.value == Decimal("1000")


@pytest.mark.django_db
def test_objective_requires_key_result_and_detects_delay() -> None:
    org = _make_org("okr")
    indicator = _make_indicator(org)

    objective = create_objective(
        organization_id=str(org.id),
        label="Croissance",
        owner="CEO",
        horizon=date.today() - timedelta(days=1),
    )
    with pytest.raises(ValueError, match="at least one key result"):
        activate_objective(objective_id=str(objective.id))

    add_key_result(objective_id=str(objective.id), indicator_id=str(indicator.id), target_value=Decimal("1000"))
    activate_objective(objective_id=str(objective.id))

    record_manual_value(definition_id=str(indicator.id), period="2026-07", value=Decimal("500"))
    assert objective_progress(objective_id=str(objective.id)) == Decimal("50.00")
    assert is_objective_late(objective_id=str(objective.id), as_of=date.today()) is True

    record_manual_value(definition_id=str(indicator.id), period="2026-08", value=Decimal("1200"))
    assert objective_progress(objective_id=str(objective.id)) == Decimal("100.00")
    assert is_objective_late(objective_id=str(objective.id), as_of=date.today()) is False


@pytest.mark.django_db
def test_budget_approval_freezes_version_and_overspend_visible() -> None:
    org = _make_org("budget")
    budget = create_budget(
        organization_id=str(org.id),
        label="Budget 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    version = budget.versions.get(version=1)

    with pytest.raises(ValueError, match="empty budget"):
        approve_version(version_id=str(version.id))

    set_budget_line(version_id=str(version.id), axis="marketing", amount=Decimal("10000.00"))
    set_budget_line(version_id=str(version.id), axis="it", amount=Decimal("5000.00"))
    approve_version(version_id=str(version.id))

    with pytest.raises(ValueError, match="frozen"):
        set_budget_line(version_id=str(version.id), axis="marketing", amount=Decimal("99999.00"))

    revision = create_revision(budget_id=str(budget.id))
    assert revision.version == 2
    assert revision.lines.count() == 2  # explicit revision copies lines

    record_actual(budget_id=str(budget.id), axis="marketing", amount=Decimal("7000.00"))
    record_actual(budget_id=str(budget.id), axis="it", amount=Decimal("6500.00"))

    availability = budget_availability(budget_id=str(budget.id))
    assert availability["marketing"]["available"] == Decimal("3000.00")
    assert availability["it"]["available"] == Decimal("-1500.00")
    assert overspent_axes(budget_id=str(budget.id)) == ["it"]
