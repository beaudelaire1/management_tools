import uuid

from django.db import models


class Risk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="risks"
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    owner_name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="open")  # open | closed
    created_at = models.DateTimeField(auto_now_add=True)


class RiskAssessment(models.Model):
    """Dated assessments accumulate: the rating history is never overwritten (spec P11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="assessments")
    assessed_on = models.DateField()
    impact = models.PositiveSmallIntegerField()  # 1..5
    probability = models.PositiveSmallIntegerField()  # 1..5
    residual_impact = models.PositiveSmallIntegerField()
    residual_probability = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(impact__gte=1, impact__lte=5, probability__gte=1, probability__lte=5),
                name="ck_assessment_scale",
            )
        ]


class Control(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="controls")
    name = models.CharField(max_length=255)
    frequency_days = models.PositiveIntegerField()
    last_executed_on = models.DateField(null=True, blank=True)


class ControlExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="executions")
    executed_on = models.DateField()
    evidence = models.CharField(max_length=500)


class Incident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="risk_incidents"
    )
    risk = models.ForeignKey(Risk, null=True, blank=True, on_delete=models.PROTECT, related_name="incidents")
    happened_at = models.DateTimeField()
    description = models.CharField(max_length=500)
