import uuid

from django.db import models


class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    party = models.ForeignKey(
        "management_parties.Party",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    sales_order = models.OneToOneField(
        "management_sales.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    number = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, default="draft")  # draft | issued
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")
    # Snapshots frozen at issuance (spec 4.4): identities as they were at that moment.
    seller_name = models.CharField(max_length=255, blank=True)
    buyer_name = models.CharField(max_length=255, blank=True)
    total_excl_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_incl_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"],
                condition=~models.Q(number=""),
                name="uq_invoice_org_number",
            )
        ]

    def save(self, *args, **kwargs):
        if self._state.adding and self.status != "draft":
            raise ValueError("An invoice must be created as a draft and issued through the issuance service.")
        if not self._state.adding:
            original = Invoice.objects.get(pk=self.pk)
            if original.status == "issued":
                raise ValueError("An issued invoice is immutable; correct it with a credit note.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == "issued":
            raise ValueError("An issued invoice can never be deleted.")
        return super().delete(*args, **kwargs)


class InvoiceLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invoice", "position"], name="uq_invoice_line_position")
        ]

    def save(self, *args, **kwargs):
        if Invoice.objects.filter(id=self.invoice_id, status="issued").exists():
            raise ValueError("Lines of an issued invoice are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if Invoice.objects.filter(id=self.invoice_id, status="issued").exists():
            raise ValueError("Lines of an issued invoice are immutable.")
        return super().delete(*args, **kwargs)


class CreditNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="credit_notes")
    number = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invoice", "number"], name="uq_credit_note_invoice_number"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_credit_note_positive"),
        ]
