from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.billing.services import (
    create_credit_note,
    create_invoice_from_order,
    invoice_remaining,
    issue_invoice,
)
from modular_brix.finance.payments.services import allocate_payment, payment_unallocated, register_payment
from modular_brix.finance.receivables.services import (
    aging_buckets,
    open_dispute,
    resolve_dispute,
    send_due_reminders,
)
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.management.parties.services import create_party
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    send_quote,
)


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"FIN-{suffix}",
        country_code="FR",
    )


def _issued_invoice(org, party, quantity="2", unit_price="500.00", tax_rate="20"):
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation",
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        tax_rate=Decimal(tax_rate),
    )
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="preuve")
    order = convert_quote_to_order(quote_id=str(quote.id))
    invoice = create_invoice_from_order(order_id=str(order.id))
    return issue_invoice(invoice_id=str(invoice.id))


@pytest.mark.django_db
def test_invoice_issue_assigns_sequential_numbers_and_freezes_snapshot() -> None:
    org = _make_org("inv-seq")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client F")

    invoice_1 = _issued_invoice(org, party)
    invoice_2 = _issued_invoice(org, party)

    year = str(timezone.now().year)
    assert invoice_1.number == f"INV-{year}-000001"
    assert invoice_2.number == f"INV-{year}-000002"  # chronological, continuous
    assert invoice_1.seller_name == org.legal_name
    assert invoice_1.buyer_name == "Client F"
    assert invoice_1.total_incl_tax == Decimal("1200.00")  # 2*500 + 20%


@pytest.mark.django_db
def test_issued_invoice_is_immutable_and_undeletable() -> None:
    org = _make_org("inv-immutable")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client I")
    invoice = _issued_invoice(org, party)

    invoice.buyer_name = "Falsifié"
    with pytest.raises(ValueError, match="immutable"):
        invoice.save()

    with pytest.raises(ValueError, match="never be deleted"):
        invoice.delete()

    fetched = Invoice.objects.get(id=invoice.id)
    assert fetched.buyer_name == "Client I"  # snapshot intact

    with pytest.raises(ValueError, match="draft invoice"):
        issue_invoice(invoice_id=str(invoice.id))  # no double issuance


@pytest.mark.django_db
def test_credit_note_cannot_exceed_invoice() -> None:
    org = _make_org("credit-cap")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client C")
    invoice = _issued_invoice(org, party)  # 1200.00

    create_credit_note(invoice_id=str(invoice.id), amount=Decimal("700.00"), reason="Remise commerciale")
    with pytest.raises(ValueError, match="exceeds creditable"):
        create_credit_note(invoice_id=str(invoice.id), amount=Decimal("600.00"), reason="Trop")

    create_credit_note(invoice_id=str(invoice.id), amount=Decimal("500.00"), reason="Solde")
    assert invoice_remaining(Invoice.objects.get(id=invoice.id)) == Decimal("0.00")


@pytest.mark.django_db
def test_payment_registration_is_idempotent_on_replay() -> None:
    org = _make_org("pay-idem")
    payment_1 = register_payment(
        organization_id=str(org.id),
        amount=Decimal("100.00"),
        method="transfer",
        idempotency_key="webhook-evt-42",
    )
    payment_2 = register_payment(
        organization_id=str(org.id),
        amount=Decimal("100.00"),
        method="transfer",
        idempotency_key="webhook-evt-42",
    )
    assert payment_1.id == payment_2.id  # double webhook, single payment


@pytest.mark.django_db
def test_allocation_caps_payment_and_invoice() -> None:
    org = _make_org("alloc-caps")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client P")
    invoice = _issued_invoice(org, party)  # 1200.00

    payment = register_payment(
        organization_id=str(org.id),
        amount=Decimal("800.00"),
        method="transfer",
        idempotency_key="pay-1",
        party_id=str(party.id),
    )

    with pytest.raises(ValueError, match="exceeds unallocated payment"):
        allocate_payment(payment_id=str(payment.id), invoice_id=str(invoice.id), amount=Decimal("900.00"))

    allocate_payment(payment_id=str(payment.id), invoice_id=str(invoice.id), amount=Decimal("800.00"))
    assert payment_unallocated(payment) == Decimal("0.00")
    assert invoice_remaining(Invoice.objects.get(id=invoice.id)) == Decimal("400.00")

    payment_2 = register_payment(
        organization_id=str(org.id),
        amount=Decimal("1000.00"),
        method="transfer",
        idempotency_key="pay-2",
    )
    with pytest.raises(ValueError, match="exceeds invoice remaining"):
        allocate_payment(payment_id=str(payment_2.id), invoice_id=str(invoice.id), amount=Decimal("500.00"))


@pytest.mark.django_db
def test_aging_and_reminders_respect_disputes_and_payments() -> None:
    org = _make_org("aging")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client R")

    overdue = _issued_invoice(org, party)  # due in 30 days
    disputed = _issued_invoice(org, party)
    paid = _issued_invoice(org, party)

    as_of = date.today() + timedelta(days=45)  # all invoices 15 days overdue

    payment = register_payment(
        organization_id=str(org.id),
        amount=Decimal("1200.00"),
        method="transfer",
        idempotency_key="pay-full",
    )
    allocate_payment(payment_id=str(payment.id), invoice_id=str(paid.id), amount=Decimal("1200.00"))
    dispute = open_dispute(invoice_id=str(disputed.id), reason="Prestation contestée")

    buckets = aging_buckets(organization_id=str(org.id), as_of=as_of)
    assert buckets["1-30"] == Decimal("2400.00")  # overdue + disputed, paid excluded
    assert buckets["current"] == Decimal("0.00")

    reminders = send_due_reminders(organization_id=str(org.id), as_of=as_of)
    reminded_invoices = {r.invoice_id for r in reminders}
    assert overdue.id in reminded_invoices
    assert disputed.id not in reminded_invoices  # suspended by open dispute
    assert paid.id not in reminded_invoices  # paid leaves the reminder cycle

    resolve_dispute(dispute_id=str(dispute.id))
    second_wave = send_due_reminders(organization_id=str(org.id), as_of=as_of)
    assert {r.invoice_id for r in second_wave} == {overdue.id, disputed.id}
    assert [r.level for r in second_wave if r.invoice_id == overdue.id] == [2]


@pytest.mark.django_db
def test_end_to_end_quote_to_payment_reconciliation() -> None:
    """Global acceptance path (spec 13.2-4): quote -> order -> invoice -> payment -> balance zero."""
    org = _make_org("e2e")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client E2E")

    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Développement",
        quantity=Decimal("10"),
        unit_price=Decimal("650.00"),
        tax_rate=Decimal("20"),
    )
    sent = send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="bon pour accord")
    order = convert_quote_to_order(quote_id=str(quote.id))
    invoice = issue_invoice(invoice_id=str(create_invoice_from_order(order_id=str(order.id)).id))

    # Same monetary result across quote, order, and invoice (spec 11.2).
    assert sent.total_incl_tax == order.total_incl_tax == invoice.total_incl_tax == Decimal("7800.00")

    payment = register_payment(
        organization_id=str(org.id),
        amount=Decimal("7800.00"),
        method="transfer",
        idempotency_key="e2e-payment",
        party_id=str(party.id),
    )
    allocate_payment(payment_id=str(payment.id), invoice_id=str(invoice.id), amount=Decimal("7800.00"))

    assert invoice_remaining(Invoice.objects.get(id=invoice.id)) == Decimal("0.00")
    assert send_due_reminders(organization_id=str(org.id), as_of=date.today() + timedelta(days=60)) == []
