import uuid

from django.db import models


class ExpenseReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="expense_reports"
    )
    submitted_by = models.ForeignKey(
        "foundation_accounts.Membership", on_delete=models.PROTECT, related_name="expense_reports"
    )
    status = models.CharField(max_length=16, default="draft")  # draft | submitted | approved
    approved_by = models.ForeignKey(
        "foundation_accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_expense_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="expenses")
    expense_date = models.DateField()
    category = models.CharField(max_length=64)
    description = models.CharField(max_length=255)
    amount_incl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    recoverable_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipt_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_incl_tax__gt=0), name="ck_expense_positive"),
            models.CheckConstraint(
                condition=models.Q(recoverable_vat__lte=models.F("amount_incl_tax")),
                name="ck_expense_vat_capped",
            ),
        ]


class Reimbursement(models.Model):
    """One reimbursement per report: paying an expense report twice is structurally impossible."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.OneToOneField(ExpenseReport, on_delete=models.PROTECT, related_name="reimbursement")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
