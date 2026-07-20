from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.expenses.models import Expense
from modular_brix.finance.payables.models import SupplierInvoice

from .models import TaxAdjustment, TaxPeriod, TaxRate, TaxReturn


def rate_at(*, organization_id: str, code: str, on_day: date) -> Decimal:
    """The historical rate applicable at a date is always retrievable (spec C11)."""
    rate = (
        TaxRate.objects.filter(organization_id=organization_id, code=code, valid_from__lte=on_day)
        .order_by("-valid_from")
        .first()
    )
    if rate is None:
        raise ValueError(f"No tax rate {code} effective on {on_day}.")
    return rate.rate


def _collected(organization_id: str, period: TaxPeriod) -> Decimal:
    total = Invoice.objects.filter(
        organization_id=organization_id,
        status="issued",
        issue_date__gte=period.starts_on,
        issue_date__lte=period.ends_on,
    ).aggregate(total=Sum("total_tax"))["total"]
    return total or Decimal("0.00")


def _deductible(organization_id: str, period: TaxPeriod) -> Decimal:
    supplier = SupplierInvoice.objects.filter(
        organization_id=organization_id,
        status__in=("validated", "paid"),
        invoice_date__gte=period.starts_on,
        invoice_date__lte=period.ends_on,
    ).aggregate(total=Sum("tax_amount"))["total"] or Decimal("0.00")
    expenses = Expense.objects.filter(
        report__organization_id=organization_id,
        report__status="approved",
        expense_date__gte=period.starts_on,
        expense_date__lte=period.ends_on,
    ).aggregate(total=Sum("recoverable_vat"))["total"] or Decimal("0.00")
    return supplier + expenses


@transaction.atomic
def prepare_return(*, period_id: str) -> TaxReturn:
    """Collected and deductible bases come straight from the source documents, so the
    return always reconciles to them; re-preparing replaces a prepared return."""
    period = TaxPeriod.objects.select_for_update().get(id=period_id)
    existing = TaxReturn.objects.filter(period=period).first()
    if existing is not None:
        if existing.status == "validated":
            raise ValueError("This period already has a validated return.")
        existing.delete()
    collected = _collected(str(period.organization_id), period)
    deductible = _deductible(str(period.organization_id), period)
    return TaxReturn.objects.create(
        period=period, collected=collected, deductible=deductible, net_due=collected - deductible
    )


@transaction.atomic
def validate_return(*, return_id: str) -> TaxReturn:
    tax_return = TaxReturn.objects.select_for_update().get(id=return_id)
    if tax_return.status != "prepared":
        raise ValueError("Only a prepared return can be validated.")
    tax_return.status = "validated"
    tax_return.save()
    return tax_return


@transaction.atomic
def add_adjustment(*, return_id: str, amount: Decimal, reason: str) -> TaxAdjustment:
    """Adjustments carry their explanation; unexplained gaps are impossible (spec C11)."""
    if not reason.strip():
        raise ValueError("A tax adjustment requires a reason.")
    tax_return = TaxReturn.objects.get(id=return_id)
    return TaxAdjustment.objects.create(tax_return=tax_return, amount=amount, reason=reason.strip())
