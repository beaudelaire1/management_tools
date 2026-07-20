import uuid

from django.db import models

MOVEMENT_IMMUTABLE_ERROR = "A stock movement is append-only; correct it with an opposite movement."


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="warehouses"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_warehouse_org_code")
        ]


class StockMovement(models.Model):
    """Append-only ledger of quantities; stock levels are always computed from it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="stock_movements"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    item = models.ForeignKey(
        "management_catalog.CatalogItem", on_delete=models.PROTECT, related_name="stock_movements"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)  # signed: in > 0, out < 0
    reason = models.CharField(max_length=64)  # receipt | delivery | consumption | adjustment | transfer
    reference = models.CharField(max_length=128, blank=True)
    moved_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(MOVEMENT_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(MOVEMENT_IMMUTABLE_ERROR)


class StockReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="stock_reservations"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="reservations")
    item = models.ForeignKey(
        "management_catalog.CatalogItem", on_delete=models.PROTECT, related_name="stock_reservations"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    status = models.CharField(max_length=16, default="active")  # active | released | consumed
    reference = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_reservation_positive")
        ]


class InventoryCount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="inventory_counts")
    item = models.ForeignKey(
        "management_catalog.CatalogItem", on_delete=models.PROTECT, related_name="inventory_counts"
    )
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    justification = models.CharField(max_length=500)
    adjustment = models.OneToOneField(
        StockMovement, null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_count"
    )
    counted_at = models.DateTimeField(auto_now_add=True)
