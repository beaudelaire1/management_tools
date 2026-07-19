import uuid

from django.db import models


class CatalogItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="catalog_items",
    )
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=255)
    item_type = models.CharField(max_length=16, default="service")  # product | service
    default_tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_catalog_item_org_code")
        ]


class Price(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="prices")
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(max_length=3, default="EUR")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "currency", "valid_from"], name="uq_price_item_currency_from")
        ]
