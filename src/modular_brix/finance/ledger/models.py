import uuid

from django.db import models

VALIDATED_ENTRY_IMMUTABLE_ERROR = "A validated journal entry is immutable; correct it with a reversal."


class FiscalYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="fiscal_years"
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, default="open")  # open | closed

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "starts_on"], name="uq_fiscal_year_start")
        ]


class AccountingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name="periods")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, default="open")  # open | locked


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="gl_accounts"
    )
    code = models.CharField(max_length=16)
    label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_gl_account_code")
        ]


class Journal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="journals"
    )
    code = models.CharField(max_length=8)
    label = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_journal_code")
        ]


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="journal_entries"
    )
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="entries")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="entries")
    entry_date = models.DateField()
    reference = models.CharField(max_length=128, blank=True)
    label = models.CharField(max_length=255)
    number = models.CharField(max_length=32, blank=True)  # allocated at validation
    status = models.CharField(max_length=16, default="draft")  # draft | validated
    validated_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "journal", "number"],
                condition=~models.Q(number=""),
                name="uq_entry_journal_number",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = JournalEntry.objects.get(pk=self.pk)
            if original.status == "validated":
                raise ValueError(VALIDATED_ENTRY_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == "validated":
            raise ValueError(VALIDATED_ENTRY_IMMUTABLE_ERROR)
        return super().delete(*args, **kwargs)


class JournalEntryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    label = models.CharField(max_length=255, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "position"], name="uq_entry_line_position"),
            models.CheckConstraint(
                condition=(
                    models.Q(debit__gte=0, credit__gte=0)
                    & ~models.Q(debit__gt=0, credit__gt=0)
                    & ~models.Q(debit=0, credit=0)
                ),
                name="ck_entry_line_single_side",
            ),
        ]

    def save(self, *args, **kwargs):
        if JournalEntry.objects.filter(id=self.entry_id, status="validated").exists():
            raise ValueError(VALIDATED_ENTRY_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if JournalEntry.objects.filter(id=self.entry_id, status="validated").exists():
            raise ValueError(VALIDATED_ENTRY_IMMUTABLE_ERROR)
        return super().delete(*args, **kwargs)
