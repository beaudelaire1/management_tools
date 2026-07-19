import uuid

from django.db import models


class FixedAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="fixed_assets"
    )
    name = models.CharField(max_length=255)
    acquisition_cost = models.DecimalField(max_digits=14, decimal_places=2)
    in_service_on = models.DateField()
    useful_life_months = models.PositiveIntegerField()
    status = models.CharField(max_length=16, default="active")  # active | disposed
    operational_asset = models.OneToOneField(
        "management_assets.Asset",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_asset",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(acquisition_cost__gt=0), name="ck_asset_cost_positive")
        ]


class DepreciationPeriod(models.Model):
    """One monthly charge per asset and period: double posting is structurally impossible."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="depreciation_periods")
    period = models.CharField(max_length=7)  # YYYY-MM
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "period"], name="uq_depreciation_asset_period")
        ]


class AssetDisposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.OneToOneField(FixedAsset, on_delete=models.PROTECT, related_name="disposal")
    disposed_on = models.DateField()
    proceeds = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_book_value = models.DecimalField(max_digits=14, decimal_places=2)
