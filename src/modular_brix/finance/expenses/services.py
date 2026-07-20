from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet, Sum

from .models import Expense, ExpenseReport, Reimbursement

RECEIPT_REQUIRED_FROM = Decimal("30.00")


@transaction.atomic
def add_expense(
    *,
    report_id: str,
    expense_date: date,
    category: str,
    description: str,
    amount_incl_tax: Decimal,
    recoverable_vat: Decimal = Decimal("0.00"),
    receipt_reference: str = "",
) -> Expense:
    report = ExpenseReport.objects.select_for_update().get(id=report_id)
    if report.status != "draft":
        raise ValueError("Expenses can only be added to a draft report.")
    if amount_incl_tax <= 0:
        raise ValueError("An expense amount must be positive.")
    if recoverable_vat > amount_incl_tax:
        raise ValueError("Recoverable VAT cannot exceed the expense amount.")
    if amount_incl_tax >= RECEIPT_REQUIRED_FROM and not receipt_reference.strip():
        raise ValueError(f"A receipt is required from {RECEIPT_REQUIRED_FROM} upward.")
    return Expense.objects.create(
        report=report,
        expense_date=expense_date,
        category=category,
        description=description,
        amount_incl_tax=amount_incl_tax,
        recoverable_vat=recoverable_vat,
        receipt_reference=receipt_reference.strip(),
    )


def find_duplicate_expenses(*, organization_id: str, expense_date: date, amount_incl_tax: Decimal) -> QuerySet[Expense]:
    """Same organization, date and amount: flagged for review before approval."""
    return Expense.objects.filter(
        report__organization_id=organization_id,
        expense_date=expense_date,
        amount_incl_tax=amount_incl_tax,
    )


@transaction.atomic
def submit_report(*, report_id: str) -> ExpenseReport:
    report = ExpenseReport.objects.select_for_update().get(id=report_id)
    if report.status != "draft":
        raise ValueError("Only a draft expense report can be submitted.")
    if not report.expenses.exists():
        raise ValueError("An empty expense report cannot be submitted.")
    report.status = "submitted"
    report.save(update_fields=["status"])
    return report


@transaction.atomic
def approve_report(*, report_id: str, approver_membership_id: str) -> ExpenseReport:
    """Approver/beneficiary separation (spec C04)."""
    report = ExpenseReport.objects.select_for_update().get(id=report_id)
    if report.status != "submitted":
        raise ValueError("Only a submitted expense report can be approved.")
    if str(report.submitted_by_id) == str(approver_membership_id):
        raise ValueError("An expense report cannot be approved by its beneficiary.")
    report.status = "approved"
    report.approved_by_id = approver_membership_id
    report.save(update_fields=["status", "approved_by"])
    return report


def report_total(report: ExpenseReport) -> Decimal:
    total = report.expenses.aggregate(total=Sum("amount_incl_tax"))["total"]
    return total or Decimal("0.00")


@transaction.atomic
def reimburse_report(*, report_id: str) -> Reimbursement:
    """Reimbursement happens once, for the exact approved total."""
    report = ExpenseReport.objects.select_for_update().get(id=report_id)
    if report.status != "approved":
        raise ValueError("Only an approved expense report can be reimbursed.")
    if Reimbursement.objects.filter(report=report).exists():
        raise ValueError("This expense report has already been reimbursed.")
    return Reimbursement.objects.create(report=report, amount=report_total(report))
