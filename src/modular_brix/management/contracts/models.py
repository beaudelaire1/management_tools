import uuid

from django.db import models

SIGNED_VERSION_IMMUTABLE_ERROR = "A signed contract version is frozen; changes require a new version."


class Contract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="contracts"
    )
    party = models.ForeignKey(
        "management_parties.Party", on_delete=models.PROTECT, related_name="contracts"
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=16, default="draft")  # draft | active | terminated
    notice_days = models.PositiveIntegerField(default=30)
    ends_on = models.DateField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ContractVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    terms = models.TextField()
    signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contract", "version_number"], name="uq_contract_version")
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = ContractVersion.objects.get(pk=self.pk)
            if original.signed_at is not None:
                raise ValueError(SIGNED_VERSION_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.signed_at is not None:
            raise ValueError(SIGNED_VERSION_IMMUTABLE_ERROR)
        return super().delete(*args, **kwargs)


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="subscriptions")
    item = models.ForeignKey(
        "management_catalog.CatalogItem", on_delete=models.PROTECT, related_name="subscriptions"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3)
    is_active = models.BooleanField(default=True)


class SubscriptionInvoiceRun(models.Model):
    """One billing run per contract and period: recurring billing is idempotent by design."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="invoice_runs")
    period = models.CharField(max_length=7)  # YYYY-MM
    invoice = models.ForeignKey(
        "finance_billing.Invoice", on_delete=models.PROTECT, related_name="subscription_runs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contract", "period"], name="uq_subscription_run_period")
        ]
