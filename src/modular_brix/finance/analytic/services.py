from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modular_brix.finance.ledger.models import JournalEntryLine

from .models import AnalyticAccount, AnalyticAllocation


@transaction.atomic
def allocate_line(*, line_id: str, splits: dict[str, Decimal]) -> list[AnalyticAllocation]:
    """Split a ledger line over analytic accounts of one axis; percentages total exactly 100.

    Re-allocating supersedes the previous split instead of deleting it, so the
    history of who carried the amount stays readable (spec C10).
    """
    line = JournalEntryLine.objects.get(id=line_id)
    if not splits:
        raise ValueError("An allocation needs at least one split.")
    total = sum(splits.values())
    if total != Decimal("100"):
        raise ValueError(f"Allocation percentages must total 100 (got {total}).")
    accounts = [AnalyticAccount.objects.select_related("axis").get(id=account_id) for account_id in splits]
    axes = {account.axis_id for account in accounts}
    if len(axes) != 1:
        raise ValueError("One allocation covers exactly one analytic axis.")
    organization_id = accounts[0].axis.organization_id
    if str(organization_id) != str(line.entry.organization_id):
        raise ValueError("Analytic accounts must belong to the entry organization.")
    AnalyticAllocation.objects.filter(
        line=line, analytic_account__axis_id=accounts[0].axis_id, superseded_at__isnull=True
    ).update(superseded_at=timezone.now())
    return [
        AnalyticAllocation.objects.create(line=line, analytic_account=account, percent=splits[str(account.id)])
        for account in accounts
    ]


def line_amount(line: JournalEntryLine) -> Decimal:
    return line.debit or line.credit


def analytic_total(*, analytic_account_id: str) -> Decimal:
    """Amounts carried by an analytic account, from validated entries only."""
    total = Decimal("0.00")
    allocations = AnalyticAllocation.objects.filter(
        analytic_account_id=analytic_account_id, superseded_at__isnull=True, line__entry__status="validated"
    ).select_related("line")
    for allocation in allocations:
        total += (line_amount(allocation.line) * allocation.percent / Decimal("100")).quantize(Decimal("0.01"))
    return total


def unallocated_lines(*, organization_id: str, axis_id: str) -> list[JournalEntryLine]:
    """Validated lines with no live split on the axis: visible, never silently absorbed."""
    lines = JournalEntryLine.objects.filter(entry__organization_id=organization_id, entry__status="validated")
    return [
        line
        for line in lines
        if not line.analytic_allocations.filter(
            analytic_account__axis_id=axis_id, superseded_at__isnull=True
        ).exists()
    ]
