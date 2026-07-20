import uuid

from django.db import models


class PurchaseRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="purchase_requests"
    )
    requested_by = models.ForeignKey(
        "foundation_accounts.Membership", on_delete=models.PROTECT, related_name="purchase_requests"
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="draft")  # draft | submitted | approved | rejected
    approved_by = models.ForeignKey(
        "foundation_accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_purchase_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PurchaseRequestLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["request", "position"], name="uq_purchase_request_line_position")
        ]


class PurchaseOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    supplier = models.ForeignKey(
        "management_parties.Party", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    request = models.OneToOneField(
        PurchaseRequest, null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_order"
    )
    number = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default="open")  # open | received | closed
    currency = models.CharField(max_length=3, default="EUR")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="uq_purchase_order_org_number")
        ]


class PurchaseOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "position"], name="uq_purchase_order_line_position")
        ]


class GoodsReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=500, blank=True)


class GoodsReceiptLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_receipt_line_positive")
        ]
