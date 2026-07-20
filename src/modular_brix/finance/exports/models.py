import uuid

from django.db import models


class FECExport(models.Model):
    """One FEC per fiscal year; the file content and its fingerprint are stored (spec C15)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="fec_exports"
    )
    fiscal_year = models.ForeignKey(
        "finance_ledger.FiscalYear", on_delete=models.PROTECT, related_name="fec_exports"
    )
    content = models.TextField()
    content_hash = models.CharField(max_length=64)
    generated_at = models.DateTimeField(auto_now_add=True)


class ExportIssue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    export = models.ForeignKey(FECExport, on_delete=models.CASCADE, related_name="issues")
    severity = models.CharField(max_length=16)  # warning | error
    message = models.CharField(max_length=500)
