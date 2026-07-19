import uuid

from django.db import models


class Forecast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="forecasts",
    )
    label = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class ForecastVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forecast = models.ForeignKey(Forecast, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    assumptions = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["forecast", "version"], name="uq_forecast_version")
        ]


class ForecastLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(ForecastVersion, on_delete=models.CASCADE, related_name="lines")
    period = models.CharField(max_length=16)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["version", "period"], name="uq_forecast_line_period")
        ]
