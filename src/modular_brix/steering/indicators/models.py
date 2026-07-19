import uuid

from django.db import models


class IndicatorDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="indicator_definitions",
    )
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=255)
    unit = models.CharField(max_length=32)
    source = models.CharField(max_length=120)
    frequency = models.CharField(max_length=24)  # daily | weekly | monthly | quarterly | yearly
    owner = models.CharField(max_length=120)
    formula_code = models.CharField(max_length=48, blank=True)
    formula_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_indicator_org_code")
        ]


class IndicatorValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(IndicatorDefinition, on_delete=models.CASCADE, related_name="values")
    period = models.CharField(max_length=16)  # e.g. 2026-07 or 2026-Q3
    value = models.DecimalField(max_digits=16, decimal_places=4)
    origin = models.CharField(max_length=16)  # manual | computed | import
    inputs = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["definition", "period"], name="uq_indicator_value_period")
        ]
