"""Lot 6 finance bricks (C04-C07): acceptance-criteria tests."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from modular_brix.finance.banking.models import FinancialAccount
from modular_brix.finance.banking.services import (
    import_statement,
    match_transaction,
    unmatch,
    unreconciled_transactions,
)
from modular_brix.finance.billing.services import create_invoice_from_order, issue_invoice
from modular_brix.finance.expenses.models import ExpenseReport
from modular_brix.finance.expenses.services import (
    add_expense,
    approve_report,
    find_duplicate_expenses,
    reimburse_report,
    submit_report,
)
from modular_brix.finance.payables.services import (
    mark_paid,
    propose_payments,
    register_supplier_invoice,
    three_way_match,
    validate_invoice,
)
from modular_brix.finance.payments.services import register_payment
from modular_brix.finance.preaccounting.models import AccountingMapping
from modular_brix.finance.preaccounting.services import (
    add_comment,
    build_batch,
    missing_documents,
    resolve_comment,
    transmit_batch,
)
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.management.parties.services import create_party
from modular_brix.management.purchasing.models import PurchaseRequest, PurchaseRequestLine
from modular_brix.management.purchasing.services import (
    approve_request,
    create_order_from_request,
    receive_goods,
    submit_request,
)
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    send_quote,
)


def _org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"fin-{suffix}",
        legal_name=f"Fin {suffix}",
        legal_identifier=f"FIN2-{suffix}",
        country_code="FR",
    )


def _membership(org, suffix: str):
    user = get_user_model().objects.create_user(username=f"fin_{suffix}", password="StrongPass123!")
    return user.memberships.create(organization=org)


# --- C04 expenses ---------------------------------------------------------


@pytest.mark.django_db
def test_expense_report_receipt_threshold_approval_separation_single_reimbursement() -> None:
    org = _org("c04")
    submitter = _membership(org, "c04-s")
    approver = _membership(org, "c04-a")
    report = ExpenseReport.objects.create(organization=org, submitted_by=submitter)

    with pytest.raises(ValueError, match="receipt is required"):
        add_expense(
            report_id=str(report.id),
            expense_date=date(2026, 7, 1),
            category="restauration",
            description="Déjeuner client",
            amount_incl_tax=Decimal("45.00"),
        )
    add_expense(
        report_id=str(report.id),
        expense_date=date(2026, 7, 1),
        category="restauration",
        description="Déjeuner client",
        amount_incl_tax=Decimal("45.00"),
        recoverable_vat=Decimal("4.09"),
        receipt_reference="TICKET-88",
    )
    with pytest.raises(ValueError, match="cannot exceed"):
        add_expense(
            report_id=str(report.id),
            expense_date=date(2026, 7, 2),
            category="transport",
            description="Taxi",
            amount_incl_tax=Decimal("20.00"),
            recoverable_vat=Decimal("25.00"),
        )

    assert find_duplicate_expenses(
        organization_id=str(org.id), expense_date=date(2026, 7, 1), amount_incl_tax=Decimal("45.00")
    ).count() == 1

    submit_report(report_id=str(report.id))
    with pytest.raises(ValueError, match="beneficiary"):
        approve_report(report_id=str(report.id), approver_membership_id=str(submitter.id))
    approve_report(report_id=str(report.id), approver_membership_id=str(approver.id))

    reimbursement = reimburse_report(report_id=str(report.id))
    assert reimbursement.amount == Decimal("45.00")
    with pytest.raises(ValueError, match="already been reimbursed"):
        reimburse_report(report_id=str(report.id))


# --- C05 supplier invoices ------------------------------------------------


@pytest.mark.django_db
def test_supplier_invoice_duplicates_matching_and_payment_proposal() -> None:
    org = _org("c05")
    requester = _membership(org, "c05-r")
    approver = _membership(org, "c05-a")
    supplier = create_party(organization_id=str(org.id), kind="organization", display_name="Grossiste")
    request = PurchaseRequest.objects.create(organization=org, requested_by=requester, subject="Stock")
    PurchaseRequestLine.objects.create(
        request=request, position=1, description="Pièces", quantity=Decimal("4"), unit_price=Decimal("25")
    )
    submit_request(request_id=str(request.id))
    approve_request(request_id=str(request.id), approver_membership_id=str(approver.id))
    order = create_order_from_request(request_id=str(request.id), supplier_id=str(supplier.id))

    invoice = register_supplier_invoice(
        organization_id=str(org.id),
        supplier_id=str(supplier.id),
        reference="F-2026-77",
        invoice_date=date(2026, 7, 10),
        amount_excl_tax=Decimal("100.00"),
        tax_amount=Decimal("20.00"),
        purchase_order_id=str(order.id),
    )
    with pytest.raises(ValueError, match="already registered"):
        register_supplier_invoice(
            organization_id=str(org.id),
            supplier_id=str(supplier.id),
            reference="F-2026-77",
            invoice_date=date(2026, 7, 10),
            amount_excl_tax=Decimal("100.00"),
            tax_amount=Decimal("20.00"),
        )

    # Not fully received yet: the match blocks payment.
    blocked = three_way_match(invoice_id=str(invoice.id))
    assert blocked.status == "blocked" and "not fully received" in blocked.block_reason
    assert propose_payments(organization_id=str(org.id)).lines.count() == 0

    line = order.lines.get()
    receive_goods(order_id=str(order.id), quantities={str(line.id): Decimal("4")})
    matched = three_way_match(invoice_id=str(invoice.id))
    assert matched.status == "validated"

    proposal = propose_payments(organization_id=str(org.id))
    assert [entry.invoice_id for entry in proposal.lines.all()] == [invoice.id]
    mark_paid(invoice_id=str(invoice.id))
    assert propose_payments(organization_id=str(org.id)).lines.count() == 0

    # An invoice without purchase order is validated manually before entering a proposal.
    manual = register_supplier_invoice(
        organization_id=str(org.id),
        supplier_id=str(supplier.id),
        reference="F-2026-78",
        invoice_date=date(2026, 7, 12),
        amount_excl_tax=Decimal("50.00"),
        tax_amount=Decimal("10.00"),
    )
    with pytest.raises(ValueError, match="linked purchase order"):
        three_way_match(invoice_id=str(manual.id))
    validate_invoice(invoice_id=str(manual.id))
    assert propose_payments(organization_id=str(org.id)).lines.count() == 1


# --- C06 banking ----------------------------------------------------------


@pytest.mark.django_db
def test_statement_import_idempotent_and_reconciliation_capped_and_audited() -> None:
    org = _org("c06")
    account = FinancialAccount.objects.create(organization=org, label="Compte courant")
    lines = [
        {"value_date": date(2026, 7, 1), "amount": "1200.00", "label": "VIR CLIENT"},
        {"value_date": date(2026, 7, 2), "amount": "-300.00", "label": "PRLV FOURNISSEUR"},
    ]

    statement = import_statement(
        account_id=str(account.id),
        statement_date=date(2026, 7, 3),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1900.00"),
        lines=lines,
    )
    replay = import_statement(
        account_id=str(account.id),
        statement_date=date(2026, 7, 3),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1900.00"),
        lines=lines,
    )
    assert replay.id == statement.id and statement.transactions.count() == 2

    with pytest.raises(ValueError, match="inconsistent"):
        import_statement(
            account_id=str(account.id),
            statement_date=date(2026, 7, 4),
            opening_balance=Decimal("1900.00"),
            closing_balance=Decimal("999.00"),
            lines=[{"value_date": date(2026, 7, 4), "amount": "10.00", "label": "X"}],
        )

    payment = register_payment(
        organization_id=str(org.id),
        party_id=None,
        amount=Decimal("1200.00"),
        currency="EUR",
        method="transfer",
        provider_reference="VIR-1",
        idempotency_key="bank-c06",
    )
    credit = statement.transactions.get(position=1)
    match = match_transaction(
        transaction_id=str(credit.id), payment_id=str(payment.id), amount=Decimal("1200.00")
    )
    with pytest.raises(ValueError, match="exceeds the unmatched remainder"):
        match_transaction(transaction_id=str(credit.id), payment_id=str(payment.id), amount=Decimal("1.00"))
    assert [entry.position for entry in unreconciled_transactions(statement_id=str(statement.id))] == [2]

    from modular_brix.foundation.audit.models import AuditEvent

    with pytest.raises(ValueError, match="reason"):
        unmatch(match_id=str(match.id), actor_user_id=None, reason="  ")
    unmatch(match_id=str(match.id), actor_user_id=None, reason="erreur d'affectation")
    assert AuditEvent.objects.filter(event_type="banking.transaction.unmatched").count() == 1


# --- C07 pre-accounting ---------------------------------------------------


@pytest.mark.django_db
def test_transmission_batch_is_reproducible_sourced_and_locking() -> None:
    org = _org("c07")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client C7")
    AccountingMapping.objects.create(
        organization=org, source_kind="sales_invoice", account_code="706", valid_from=date(2026, 1, 1)
    )
    AccountingMapping.objects.create(
        organization=org, source_kind="customer_payment", account_code="512", valid_from=date(2026, 1, 1)
    )
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
        tax_rate=Decimal("20"),
    )
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="ok")
    order = convert_quote_to_order(quote_id=str(quote.id))
    invoice = create_invoice_from_order(order_id=str(order.id))
    issue_invoice(invoice_id=str(invoice.id))
    register_payment(
        organization_id=str(org.id),
        party_id=str(party.id),
        amount=Decimal("600.00"),
        currency="EUR",
        method="transfer",
        provider_reference="VIR-C7",
        idempotency_key="pay-c07",
    )

    today = timezone.now().date()
    period = {"period_start": today.replace(day=1), "period_end": today}
    batch_1 = build_batch(organization_id=str(org.id), **period)
    batch_2 = build_batch(organization_id=str(org.id), **period)
    assert batch_1.content_hash == batch_2.content_hash  # reproducible
    assert batch_1.items.count() == 2
    assert all(item.source_id for item in batch_1.items.all())  # every line has its source
    assert missing_documents(batch_id=str(batch_1.id)) == []

    comment = add_comment(batch_id=str(batch_1.id), author_name="Cabinet", body="Pièce 2 illisible")
    resolve_comment(comment_id=str(comment.id))

    transmit_batch(batch_id=str(batch_1.id))
    with pytest.raises(ValueError, match="locked"):
        build_batch(organization_id=str(org.id), **period)
