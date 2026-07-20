import uuid

from django.db import models


class SupplierInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="supplier_invoices"
    )
    supplier = models.ForeignKey(
        "management_parties.Party", on_delete=models.PROTECT, related_name="supplier_invoices"
    )
    reference = models.CharField(max_length=64)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount_excl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_incl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    status = models.CharField(max_length=16, default="received")  # received | validated | blocked | paid
    block_reason = models.CharField(max_length=255, blank=True)
    purchase_order = models.ForeignKey(
        "management_purchasing.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Uniqueness supplier/reference/date makes double entry impossible (spec C05).
            models.UniqueConstraint(
                fields=["organization", "supplier", "reference", "invoice_date"],
                name="uq_supplier_invoice_identity",
            )
        ]


class PaymentProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="payment_proposals"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentProposalLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(PaymentProposal, on_delete=models.CASCADE, related_name="lines")
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.PROTECT, related_name="proposal_lines")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
