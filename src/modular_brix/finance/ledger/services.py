from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modular_brix.foundation.sequences.services import allocate_number, format_reference

from .models import Account, AccountingPeriod, JournalEntry, JournalEntryLine


def _period_for(organization_id: str, entry_date: date) -> AccountingPeriod:
    period = AccountingPeriod.objects.filter(
        fiscal_year__organization_id=organization_id,
        starts_on__lte=entry_date,
        ends_on__gte=entry_date,
    ).first()
    if period is None:
        raise ValueError(f"No accounting period covers {entry_date}.")
    if period.status != "open" or period.fiscal_year.status != "open":
        raise ValueError(f"The period covering {entry_date} is locked.")
    return period


@transaction.atomic
def create_entry(
    *,
    organization_id: str,
    journal_id: str,
    entry_date: date,
    label: str,
    lines: list[dict],
    reference: str = "",
) -> JournalEntry:
    """Double-entry invariant: total debit equals total credit, always above zero."""
    if len(lines) < 2:
        raise ValueError("A journal entry needs at least two lines.")
    total_debit = sum(Decimal(str(line.get("debit", 0))) for line in lines)
    total_credit = sum(Decimal(str(line.get("credit", 0))) for line in lines)
    if total_debit != total_credit:
        raise ValueError(f"Entry is unbalanced: debit {total_debit} differs from credit {total_credit}.")
    if total_debit <= 0:
        raise ValueError("An entry must move a positive amount.")
    period = _period_for(organization_id, entry_date)
    entry = JournalEntry.objects.create(
        organization_id=organization_id,
        journal_id=journal_id,
        period=period,
        entry_date=entry_date,
        label=label,
        reference=reference,
    )
    for position, line in enumerate(lines, start=1):
        account = Account.objects.get(id=line["account_id"])
        if str(account.organization_id) != str(organization_id):
            raise ValueError("An entry line account must belong to the same organization.")
        JournalEntryLine.objects.create(
            entry=entry,
            position=position,
            account=account,
            label=line.get("label", ""),
            debit=Decimal(str(line.get("debit", 0))),
            credit=Decimal(str(line.get("credit", 0))),
        )
    return entry


@transaction.atomic
def validate_entry(*, entry_id: str) -> JournalEntry:
    """Validation allocates the chronological number and freezes the entry forever."""
    entry = JournalEntry.objects.select_for_update().get(id=entry_id)
    if entry.status != "draft":
        raise ValueError("Only a draft entry can be validated.")
    _period_for(str(entry.organization_id), entry.entry_date)
    year = str(entry.entry_date.year)
    number = allocate_number(
        organization_id=str(entry.organization_id), code=f"gl-{entry.journal.code}", period=year
    )
    entry.number = format_reference(prefix=entry.journal.code, period=year, number=number)
    entry.status = "validated"
    entry.validated_at = timezone.now()
    entry.save()
    return entry


@transaction.atomic
def reverse_entry(*, entry_id: str, reversal_date: date, label: str = "") -> JournalEntry:
    """The only correction path for a validated entry: an opposite, linked entry."""
    original = JournalEntry.objects.get(id=entry_id)
    if original.status != "validated":
        raise ValueError("Only a validated entry can be reversed.")
    if JournalEntry.objects.filter(reversal_of=original).exists():
        raise ValueError("This entry has already been reversed.")
    reversal = create_entry(
        organization_id=str(original.organization_id),
        journal_id=str(original.journal_id),
        entry_date=reversal_date,
        label=label or f"Contrepassation {original.number}",
        reference=original.number,
        lines=[
            {
                "account_id": str(line.account_id),
                "label": line.label,
                "debit": line.credit,
                "credit": line.debit,
            }
            for line in original.lines.order_by("position")
        ],
    )
    reversal.reversal_of = original
    reversal.save(update_fields=["reversal_of"])
    return validate_entry(entry_id=str(reversal.id))


def account_balance(*, account_id: str) -> Decimal:
    """Validated entries only: the ledger never counts drafts."""
    totals = JournalEntryLine.objects.filter(account_id=account_id, entry__status="validated").aggregate(
        debit=Sum("debit"), credit=Sum("credit")
    )
    return (totals["debit"] or Decimal("0.00")) - (totals["credit"] or Decimal("0.00"))


def trial_balance(*, organization_id: str) -> list[dict]:
    """Per-account totals over validated entries; grand totals are equal by construction."""
    rows = []
    for account in Account.objects.filter(organization_id=organization_id).order_by("code"):
        totals = JournalEntryLine.objects.filter(account=account, entry__status="validated").aggregate(
            debit=Sum("debit"), credit=Sum("credit")
        )
        debit = totals["debit"] or Decimal("0.00")
        credit = totals["credit"] or Decimal("0.00")
        if debit or credit:
            rows.append({"code": account.code, "debit": debit, "credit": credit})
    return rows
