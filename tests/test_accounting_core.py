"""Lot 7 accounting bricks (C08-C13, C15): acceptance-criteria tests."""

from datetime import date
from decimal import Decimal

import pytest

from modular_brix.finance.analytic.models import AnalyticAccount, AnalyticAxis
from modular_brix.finance.analytic.services import allocate_line, analytic_total, unallocated_lines
from modular_brix.finance.closing.models import ClosingRun, ClosingTask
from modular_brix.finance.closing.services import close_run, complete_task, record_carry_forward, reopen_run
from modular_brix.finance.exports.services import FEC_HEADER, generate_fec
from modular_brix.finance.fixed_assets.models import FixedAsset
from modular_brix.finance.fixed_assets.services import (
    dispose_asset,
    linear_plan,
    net_book_value,
    post_depreciation,
)
from modular_brix.finance.ledger.models import Account, AccountingPeriod, FiscalYear, Journal
from modular_brix.finance.ledger.services import (
    account_balance,
    create_entry,
    reverse_entry,
    trial_balance,
    validate_entry,
)
from modular_brix.finance.subledger.services import (
    create_open_item,
    letter_items,
    party_balance,
    remaining_amount,
    unletter_group,
)
from modular_brix.finance.tax.models import TaxPeriod, TaxRate
from modular_brix.finance.tax.services import add_adjustment, prepare_return, rate_at, validate_return
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.management.parties.services import create_party


def _org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"acct-{suffix}",
        legal_name=f"Acct {suffix}",
        legal_identifier=f"ACCT-{suffix}",
        country_code="FR",
    )


def _ledger(org):
    year = FiscalYear.objects.create(
        organization=org, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31)
    )
    AccountingPeriod.objects.create(
        fiscal_year=year, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31)
    )
    journal = Journal.objects.create(organization=org, code="VE", label="Ventes")
    bank = Account.objects.create(organization=org, code="512", label="Banque")
    sales = Account.objects.create(organization=org, code="706", label="Prestations")
    return year, journal, bank, sales


def _balanced_entry(org, journal, bank, sales, amount="1200.00"):
    return create_entry(
        organization_id=str(org.id),
        journal_id=str(journal.id),
        entry_date=date(2026, 3, 10),
        label="Vente",
        lines=[
            {"account_id": str(bank.id), "debit": Decimal(amount)},
            {"account_id": str(sales.id), "credit": Decimal(amount)},
        ],
    )


# --- C08 general ledger ---------------------------------------------------


@pytest.mark.django_db
def test_double_entry_balance_immutability_and_reversal() -> None:
    org = _org("c08")
    _, journal, bank, sales = _ledger(org)

    with pytest.raises(ValueError, match="unbalanced"):
        create_entry(
            organization_id=str(org.id),
            journal_id=str(journal.id),
            entry_date=date(2026, 3, 10),
            label="Déséquilibrée",
            lines=[
                {"account_id": str(bank.id), "debit": Decimal("100.00")},
                {"account_id": str(sales.id), "credit": Decimal("90.00")},
            ],
        )

    entry = _balanced_entry(org, journal, bank, sales)
    validated = validate_entry(entry_id=str(entry.id))
    assert validated.number == "VE-2026-000001"  # chronological numbering

    validated.label = "Falsifiée"
    with pytest.raises(ValueError, match="immutable"):
        validated.save()
    line = validated.lines.first()
    line.debit = Decimal("1.00")
    with pytest.raises(ValueError, match="immutable"):
        line.save()

    assert account_balance(account_id=str(bank.id)) == Decimal("1200.00")
    reversal = reverse_entry(entry_id=str(validated.id), reversal_date=date(2026, 3, 31))
    assert reversal.number == "VE-2026-000002"
    with pytest.raises(ValueError, match="already been reversed"):
        reverse_entry(entry_id=str(validated.id), reversal_date=date(2026, 3, 31))
    assert account_balance(account_id=str(bank.id)) == Decimal("0.00")

    balance = trial_balance(organization_id=str(org.id))
    assert sum(row["debit"] for row in balance) == sum(row["credit"] for row in balance)


@pytest.mark.django_db
def test_locked_period_rejects_entries() -> None:
    org = _org("c08b")
    year, journal, bank, sales = _ledger(org)
    AccountingPeriod.objects.filter(fiscal_year=year).update(status="locked")
    with pytest.raises(ValueError, match="locked"):
        _balanced_entry(org, journal, bank, sales)


# --- C09 subledger --------------------------------------------------------


@pytest.mark.django_db
def test_lettering_balances_caps_and_partial_follow_up() -> None:
    org = _org("c09")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client L")
    invoice_item = create_open_item(
        organization_id=str(org.id),
        party_id=str(party.id),
        direction="debit",
        source_kind="invoice",
        source_id="inv-1",
        amount=Decimal("1000.00"),
    )
    payment_item = create_open_item(
        organization_id=str(org.id),
        party_id=str(party.id),
        direction="credit",
        source_kind="payment",
        source_id="pay-1",
        amount=Decimal("600.00"),
    )

    with pytest.raises(ValueError, match="must balance"):
        letter_items(
            organization_id=str(org.id),
            party_id=str(party.id),
            allocations={str(invoice_item.id): Decimal("700.00"), str(payment_item.id): Decimal("600.00")},
        )
    with pytest.raises(ValueError, match="exceeds the remainder"):
        letter_items(
            organization_id=str(org.id),
            party_id=str(party.id),
            allocations={str(invoice_item.id): Decimal("700.00"), str(payment_item.id): Decimal("700.00")},
        )

    group = letter_items(
        organization_id=str(org.id),
        party_id=str(party.id),
        allocations={str(invoice_item.id): Decimal("600.00"), str(payment_item.id): Decimal("600.00")},
    )
    assert remaining_amount(invoice_item) == Decimal("400.00")  # partial follow-up
    assert party_balance(organization_id=str(org.id), party_id=str(party.id)) == Decimal("400.00")

    unletter_group(group_id=str(group.id))
    assert remaining_amount(invoice_item) == Decimal("1000.00")


# --- C10 analytic ---------------------------------------------------------


@pytest.mark.django_db
def test_analytic_allocation_totals_100_and_reconciles_to_ledger() -> None:
    org = _org("c10")
    _, journal, bank, sales = _ledger(org)
    axis = AnalyticAxis.objects.create(organization=org, code="ACT", label="Activités")
    conseil = AnalyticAccount.objects.create(axis=axis, code="CONSEIL", label="Conseil")
    formation = AnalyticAccount.objects.create(axis=axis, code="FORM", label="Formation")

    entry = _balanced_entry(org, journal, bank, sales)
    validate_entry(entry_id=str(entry.id))
    sales_line = entry.lines.get(credit__gt=0)

    with pytest.raises(ValueError, match="total 100"):
        allocate_line(line_id=str(sales_line.id), splits={str(conseil.id): Decimal("70")})
    allocate_line(
        line_id=str(sales_line.id),
        splits={str(conseil.id): Decimal("70"), str(formation.id): Decimal("30")},
    )
    assert analytic_total(analytic_account_id=str(conseil.id)) == Decimal("840.00")
    assert analytic_total(analytic_account_id=str(formation.id)) == Decimal("360.00")
    # Allocated total reconciles to the ledger line amount.
    assert analytic_total(analytic_account_id=str(conseil.id)) + analytic_total(
        analytic_account_id=str(formation.id)
    ) == sales_line.credit

    remaining = unallocated_lines(organization_id=str(org.id), axis_id=str(axis.id))
    assert sales_line.id not in [line.id for line in remaining]  # bank line still unallocated
    assert len(remaining) == 1

    # Reallocation supersedes but keeps history.
    allocate_line(line_id=str(sales_line.id), splits={str(conseil.id): Decimal("100")})
    assert analytic_total(analytic_account_id=str(conseil.id)) == Decimal("1200.00")
    assert sales_line.analytic_allocations.filter(superseded_at__isnull=False).count() == 2


# --- C11 tax --------------------------------------------------------------


@pytest.mark.django_db
def test_tax_rates_are_historical_and_return_frozen_after_validation() -> None:
    org = _org("c11")
    TaxRate.objects.create(
        organization=org, code="standard", rate=Decimal("19.600"), valid_from=date(2000, 1, 1)
    )
    TaxRate.objects.create(
        organization=org, code="standard", rate=Decimal("20.000"), valid_from=date(2014, 1, 1)
    )
    assert rate_at(organization_id=str(org.id), code="standard", on_day=date(2010, 6, 1)) == Decimal("19.600")
    assert rate_at(organization_id=str(org.id), code="standard", on_day=date(2026, 6, 1)) == Decimal("20.000")

    period = TaxPeriod.objects.create(organization=org, starts_on=date(2026, 7, 1), ends_on=date(2026, 7, 31))
    tax_return = prepare_return(period_id=str(period.id))
    assert tax_return.collected == Decimal("0.00") and tax_return.net_due == Decimal("0.00")

    add_adjustment(return_id=str(tax_return.id), amount=Decimal("-12.00"), reason="Arrondi déclaratif")
    with pytest.raises(ValueError, match="reason"):
        add_adjustment(return_id=str(tax_return.id), amount=Decimal("1.00"), reason=" ")

    validate_return(return_id=str(tax_return.id))
    tax_return.refresh_from_db()
    tax_return.collected = Decimal("999.00")
    with pytest.raises(ValueError, match="frozen"):
        tax_return.save()
    with pytest.raises(ValueError, match="validated return"):
        prepare_return(period_id=str(period.id))


# --- C12 fixed assets -----------------------------------------------------


@pytest.mark.django_db
def test_depreciation_plan_sums_to_base_no_double_posting_and_nbv() -> None:
    org = _org("c12")
    asset = FixedAsset.objects.create(
        organization=org,
        name="Serveur",
        acquisition_cost=Decimal("1000.00"),
        in_service_on=date(2026, 1, 15),
        useful_life_months=36,
    )
    plan = linear_plan(asset)
    assert len(plan) == 36
    assert sum(amount for _, amount in plan) == Decimal("1000.00")  # exact, rounding absorbed

    post_depreciation(asset_id=str(asset.id), period="2026-01")
    with pytest.raises(ValueError, match="already posted"):
        post_depreciation(asset_id=str(asset.id), period="2026-01")
    with pytest.raises(ValueError, match="not part of this asset"):
        post_depreciation(asset_id=str(asset.id), period="2040-01")
    post_depreciation(asset_id=str(asset.id), period="2026-02")

    assert net_book_value(asset) == Decimal("1000.00") - Decimal("55.56")
    disposal = dispose_asset(asset_id=str(asset.id), disposed_on=date(2026, 3, 1), proceeds=Decimal("800"))
    assert disposal.net_book_value == net_book_value(asset)
    with pytest.raises(ValueError, match="disposed"):
        post_depreciation(asset_id=str(asset.id), period="2026-03")


# --- C13 closing ----------------------------------------------------------


@pytest.mark.django_db
def test_closing_blocked_by_critical_tasks_and_reopening_audited() -> None:
    org = _org("c13")
    year, journal, bank, sales = _ledger(org)
    run = ClosingRun.objects.create(fiscal_year=year)
    critical = ClosingTask.objects.create(run=run, name="Rapprochement bancaire", is_critical=True)

    with pytest.raises(ValueError, match="critical closing task"):
        close_run(run_id=str(run.id))
    with pytest.raises(ValueError, match="evidence"):
        complete_task(task_id=str(critical.id), evidence=" ", prepared_by="Alice", validated_by="Bob")
    with pytest.raises(ValueError, match="preparer"):
        complete_task(task_id=str(critical.id), evidence="PV", prepared_by="Alice", validated_by="Alice")
    complete_task(task_id=str(critical.id), evidence="PV de rapprochement", prepared_by="Alice", validated_by="Bob")

    with pytest.raises(ValueError, match="unbalanced"):
        record_carry_forward(
            run_id=str(run.id), rows=[{"account_code": "512", "debit": "100.00", "credit": "0"}]
        )
    record_carry_forward(
        run_id=str(run.id),
        rows=[
            {"account_code": "512", "debit": "100.00"},
            {"account_code": "120", "credit": "100.00"},
        ],
    )

    close_run(run_id=str(run.id))
    year.refresh_from_db()
    assert year.status == "closed"
    with pytest.raises(ValueError, match="locked"):
        _balanced_entry(org, journal, bank, sales)  # closed year rejects entries

    from modular_brix.foundation.audit.models import AuditEvent

    reopen_run(run_id=str(run.id), actor_user_id=None, reason="Erreur de provision")
    assert AuditEvent.objects.filter(event_type="closing.run.reopened").count() == 1


# --- C15 FEC --------------------------------------------------------------


@pytest.mark.django_db
def test_fec_export_is_deterministic_ordered_and_fingerprinted() -> None:
    org = _org("c15")
    year, journal, bank, sales = _ledger(org)
    entry = _balanced_entry(org, journal, bank, sales)
    validate_entry(entry_id=str(entry.id))
    draft = _balanced_entry(org, journal, bank, sales, amount="50.00")  # never exported

    export_1 = generate_fec(organization_id=str(org.id), fiscal_year_id=str(year.id))
    export_2 = generate_fec(organization_id=str(org.id), fiscal_year_id=str(year.id))
    assert export_1.content_hash == export_2.content_hash  # deterministic
    lines = export_1.content.strip().split("\r\n")
    assert lines[0] == FEC_HEADER
    assert len(lines) == 3  # header + two lines of the validated entry only
    assert "VE-2026-000001" in lines[1]
    assert "1200,00" in lines[1]
    assert str(draft.id) not in export_1.content
    assert export_1.issues.count() == 0
