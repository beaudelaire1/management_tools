import uuid

from django.db import models


class Objective(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="objectives",
    )
    label = models.CharField(max_length=255)
    owner = models.CharField(max_length=120)
    horizon = models.DateField()
    status = models.CharField(max_length=16, default="draft")  # draft | active | closed
    created_at = models.DateTimeField(auto_now_add=True)


class KeyResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="key_results")
    indicator = models.ForeignKey(
        "steering_indicators.IndicatorDefinition",
        on_delete=models.PROTECT,
        related_name="key_results",
    )
    target_value = models.DecimalField(max_digits=16, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["objective", "indicator"], name="uq_key_result_indicator"),
            models.CheckConstraint(condition=models.Q(target_value__gt=0), name="ck_key_result_target_positive"),
        ]
