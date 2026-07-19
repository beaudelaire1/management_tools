import uuid

from django.db import models


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="reports",
    )
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=255)
    dataset_key = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_report_org_code")
        ]


class ReportRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="runs")
    parameters = models.JSONField(default=dict)
    row_count = models.PositiveIntegerField()
    executed_at = models.DateTimeField(auto_now_add=True)
