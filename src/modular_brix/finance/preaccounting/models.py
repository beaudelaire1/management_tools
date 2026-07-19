import uuid

from django.db import models

LOCKED_BATCH_ERROR = "A transmitted batch is locked; corrections go through a new batch."


class AccountingMapping(models.Model):
    """Dated mapping from a business source kind to an account code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="accounting_mappings"
    )
    source_kind = models.CharField(max_length=32)  # sales_invoice | customer_payment | ...
    account_code = models.CharField(max_length=16)
    valid_from = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_kind", "valid_from"], name="uq_mapping_effective"
            )
        ]


class TransmissionBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="transmission_batches"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, default="draft")  # draft | transmitted
    content_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PreAccountingItem(models.Model):
    """Every exported line keeps a pointer to its business source (spec C07)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(TransmissionBatch, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField()
    source_kind = models.CharField(max_length=32)
    source_id = models.CharField(max_length=64)
    account_code = models.CharField(max_length=16)
    label = models.CharField(max_length=255)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["batch", "position"], name="uq_preaccounting_position")
        ]


class AccountantComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(TransmissionBatch, on_delete=models.CASCADE, related_name="comments")
    author_name = models.CharField(max_length=255)
    body = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
