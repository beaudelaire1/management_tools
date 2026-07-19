import uuid

from django.db import models


class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="budgets",
    )
    label = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)


class BudgetVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, default="draft")  # draft | approved
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["budget", "version"], name="uq_budget_version")
        ]


class BudgetLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(BudgetVersion, on_delete=models.CASCADE, related_name="lines")
    axis = models.CharField(max_length=120)  # cost center, project, activity...
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["version", "axis"], name="uq_budget_line_axis")
        ]


class BudgetActual(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="actuals")
    axis = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now_add=True)
