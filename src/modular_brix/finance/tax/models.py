import uuid

from django.db import models

VALIDATED_RETURN_ERROR = "A validated tax return is frozen; corrections go through adjustments on a new period."


class TaxRate(models.Model):
    """Dated VAT rates: the rate applicable at a date stays retrievable forever."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="tax_rates"
    )
    code = models.CharField(max_length=16)  # standard | intermediate | reduced | ...
    rate = models.DecimalField(max_digits=6, decimal_places=3)
    valid_from = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "valid_from"], name="uq_tax_rate_effective"
            )
        ]


class TaxPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="tax_periods"
    )
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "starts_on", "ends_on"], name="uq_tax_period"
            )
        ]


class TaxReturn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.OneToOneField(TaxPeriod, on_delete=models.PROTECT, related_name="tax_return")
    collected = models.DecimalField(max_digits=14, decimal_places=2)
    deductible = models.DecimalField(max_digits=14, decimal_places=2)
    net_due = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=16, default="prepared")  # prepared | validated
    prepared_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = TaxReturn.objects.get(pk=self.pk)
            if original.status == "validated":
                raise ValueError(VALIDATED_RETURN_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == "validated":
            raise ValueError(VALIDATED_RETURN_ERROR)
        return super().delete(*args, **kwargs)


class TaxAdjustment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tax_return = models.ForeignKey(TaxReturn, on_delete=models.PROTECT, related_name="adjustments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255)
