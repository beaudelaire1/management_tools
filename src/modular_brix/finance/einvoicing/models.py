import uuid

from django.db import models

PAYLOAD_FROZEN_ERROR = "An electronic invoice payload is frozen at creation."


class ProviderConfiguration(models.Model):
    """Active platform adapter per organization; switching never touches C01 (spec C14)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="einvoicing_provider"
    )
    adapter_code = models.CharField(max_length=32)


class ElectronicInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.OneToOneField(
        "finance_billing.Invoice", on_delete=models.PROTECT, related_name="electronic_invoice"
    )
    # The original structured payload is preserved exactly as built (spec C14).
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(PAYLOAD_FROZEN_ERROR)
        return super().save(*args, **kwargs)


class Transmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    electronic_invoice = models.ForeignKey(
        ElectronicInvoice, on_delete=models.PROTECT, related_name="transmissions"
    )
    adapter_code = models.CharField(max_length=32)
    idempotency_key = models.CharField(max_length=128)
    status = models.CharField(max_length=16, default="pending")  # pending | accepted | rejected
    provider_message = models.CharField(max_length=500, blank=True)
    provider_status = models.CharField(max_length=32, blank=True)
    transmitted_at = models.DateTimeField(auto_now_add=True)
    status_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["electronic_invoice", "idempotency_key"], name="uq_transmission_idempotency"
            )
        ]
