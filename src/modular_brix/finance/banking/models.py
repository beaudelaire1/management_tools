import uuid

from django.db import models


class FinancialAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="financial_accounts"
    )
    label = models.CharField(max_length=255)
    iban = models.CharField(max_length=34, blank=True)
    currency = models.CharField(max_length=3, default="EUR")


class BankStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(FinancialAccount, on_delete=models.PROTECT, related_name="statements")
    statement_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2)
    # Hash of the imported content: re-importing the same file can never duplicate it.
    import_hash = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "import_hash"], name="uq_statement_import_hash")
        ]


class BankTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="transactions")
    position = models.PositiveIntegerField()
    value_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["statement", "position"], name="uq_bank_transaction_position")
        ]


class TransactionMatch(models.Model):
    """One-to-many reconciliation between a bank transaction and payments."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(BankTransaction, on_delete=models.PROTECT, related_name="matches")
    payment = models.ForeignKey(
        "finance_payments.Payment", on_delete=models.PROTECT, related_name="bank_matches"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
