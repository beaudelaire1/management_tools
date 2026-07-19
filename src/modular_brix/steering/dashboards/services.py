from django.db import transaction

from modular_brix.foundation.permissions.policies import has_action_permission
from modular_brix.steering.indicators.models import IndicatorDefinition
from modular_brix.steering.indicators.services import latest_value

from .models import Dashboard, DashboardWidget

WIDGET_CATALOG = {"kpi", "trend", "list"}


@transaction.atomic
def add_widget(
    *,
    dashboard_id: str,
    widget_type: str,
    indicator_id: str | None = None,
    configuration: dict | None = None,
) -> DashboardWidget:
    """Only widgets from the authorized catalog can be added (spec P01)."""
    if widget_type not in WIDGET_CATALOG:
        raise ValueError(f"Widget type '{widget_type}' is not in the authorized catalog.")
    dashboard = Dashboard.objects.select_for_update().get(id=dashboard_id)
    if indicator_id is not None:
        indicator = IndicatorDefinition.objects.get(id=indicator_id)
        if indicator.organization_id != dashboard.organization_id:
            raise ValueError("A dashboard cannot reference an indicator from another organization.")
    position = dashboard.widgets.count() + 1
    return DashboardWidget.objects.create(
        dashboard=dashboard,
        widget_type=widget_type,
        indicator_id=indicator_id,
        position=position,
        configuration=configuration or {},
    )


def get_widget_data(*, widget_id: str, membership_id: str):
    """A widget never bypasses permissions: data access requires the read action."""
    widget = DashboardWidget.objects.select_related("indicator", "dashboard").get(id=widget_id)
    if widget.indicator_id is not None and widget.indicator.organization_id != widget.dashboard.organization_id:
        raise PermissionError("Widget data organization does not match its dashboard.")
    if not has_action_permission(
        membership_id=membership_id,
        action="read",
        organization_id=str(widget.dashboard.organization_id),
    ):
        raise PermissionError("Access to widget data denied by policy.")
    if widget.indicator_id is None:
        return None
    return latest_value(definition_id=str(widget.indicator_id))
