import uuid

from django.db import models


class ImportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="import_jobs",
    )
    label = models.CharField(max_length=120)
    all_or_nothing = models.BooleanField(default=True)
    status = models.CharField(max_length=24, default="pending")  # pending | rejected | completed | completed_with_errors
    created_at = models.DateTimeField(auto_now_add=True)


class ImportRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    payload = models.JSONField()
    status = models.CharField(max_length=24, default="pending")  # pending | invalid | applied | skipped
    error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "row_number"], name="uq_import_row_number")
        ]


class ExportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="export_jobs",
    )
    label = models.CharField(max_length=120)
    status = models.CharField(max_length=24, default="pending")
    row_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
