import uuid

from django.conf import settings
from django.db import models


class Dashboard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="dashboards",
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dashboards",
    )
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class DashboardWidget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    widget_type = models.CharField(max_length=24)  # kpi | trend | list
    indicator = models.ForeignKey(
        "steering_indicators.IndicatorDefinition",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="widgets",
    )
    position = models.PositiveIntegerField()
    configuration = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["dashboard", "position"], name="uq_widget_dashboard_position")
        ]
