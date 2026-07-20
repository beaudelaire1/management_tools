import uuid

from django.db import models

SIGNATURE_IMMUTABLE_ERROR = "A customer signature can never be modified or deleted."


class WorkOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="work_orders"
    )
    party = models.ForeignKey(
        "management_parties.Party", on_delete=models.PROTECT, related_name="work_orders"
    )
    project = models.ForeignKey(
        "management_projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="planned")  # planned | in_progress | closed
    created_at = models.DateTimeField(auto_now_add=True)


class Intervention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name="interventions")
    scheduled_at = models.DateTimeField()
    report = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)


class ConsumedItem(models.Model):
    """Consumption is tied one-to-one to its stock movement so stock is decremented exactly once."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.PROTECT, related_name="consumed_items")
    item = models.ForeignKey(
        "management_catalog.CatalogItem", on_delete=models.PROTECT, related_name="consumptions"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    stock_movement = models.OneToOneField(
        "management_stock.StockMovement", on_delete=models.PROTECT, related_name="consumed_item"
    )
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["intervention", "idempotency_key"], name="uq_consumption_idempotency"
            )
        ]


class CustomerSignature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.OneToOneField(Intervention, on_delete=models.PROTECT, related_name="signature")
    signed_by = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64)
    signed_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(SIGNATURE_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(SIGNATURE_IMMUTABLE_ERROR)
