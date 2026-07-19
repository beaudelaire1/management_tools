import uuid

from django.db import models


class Quote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    party = models.ForeignKey(
        "management_parties.Party",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    number = models.CharField(max_length=32)
    version = models.PositiveIntegerField(default=1)
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="next_versions",
    )
    status = models.CharField(max_length=16, default="draft")  # draft | sent | accepted | rejected
    currency = models.CharField(max_length=3, default="EUR")
    valid_until = models.DateField(null=True, blank=True)
    total_excl_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_incl_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    acceptance_proof = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "number", "version"], name="uq_quote_org_number_version")
        ]


class QuoteLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["quote", "position"], name="uq_quote_line_position")
        ]


class SalesOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    party = models.ForeignKey(
        "management_parties.Party",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    quote = models.OneToOneField(Quote, on_delete=models.PROTECT, related_name="sales_order")
    number = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default="open")  # open | fulfilled | cancelled
    currency = models.CharField(max_length=3, default="EUR")
    total_excl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2)
    total_incl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="uq_sales_order_org_number")
        ]


class SalesOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3)
    delivered_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "position"], name="uq_order_line_position"),
            models.CheckConstraint(
                condition=models.Q(delivered_quantity__lte=models.F("quantity")),
                name="ck_order_line_delivered_lte_ordered",
            ),
        ]


class Delivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="deliveries")
    created_at = models.DateTimeField(auto_now_add=True)


class DeliveryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT, related_name="delivery_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
