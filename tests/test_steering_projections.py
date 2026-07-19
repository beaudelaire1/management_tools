from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from modular_brix.finance.billing.services import create_invoice_from_order, issue_invoice
from modular_brix.finance.payments.services import allocate_payment, register_payment
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import Role
from modular_brix.foundation.permissions.services import assign_role
from modular_brix.management.crm.models import Lead
from modular_brix.management.crm.services import convert_lead_to_opportunity, lose_opportunity
from modular_brix.management.parties.services import create_party
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    send_quote,
)
from modular_brix.steering.analytics.services import loss_reasons, margin_by_party, sales_funnel
from modular_brix.steering.cashflow.services import expected_inflows, low_point_alerts
from modular_brix.steering.forecasts.models import Forecast
from modular_brix.steering.forecasts.services import build_forecast_version, compare_scenarios
from modular_brix.steering.reports.services import create_report, run_report


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"PP-{suffix}",
        country_code="FR",
    )


def _issued_invoice(org, party, unit_price="1000.00"):
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation",
        quantity=Decimal("1"),
        unit_price=Decimal(unit_price),
        tax_rate=Decimal("20"),
    )
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="ok")
    order = convert_quote_to_order(quote_id=str(quote.id))
    return issue_invoice(invoice_id=str(create_invoice_from_order(order_id=str(order.id)).id))


@pytest.mark.django_db
def test_forecast_versions_are_dated_and_reproducible() -> None:
    org = _make_org("forecast")
    forecast = Forecast.objects.create(organization=org, label="CA 2026")

    version_1 = build_forecast_version(
        forecast_id=str(forecast.id),
        base_amount=Decimal("1000.00"),
        growth_percent=Decimal("10"),
        periods=["2026-07", "2026-08", "2026-09"],
    )
    version_2 = build_forecast_version(
        forecast_id=str(forecast.id),
        base_amount=Decimal("1000.00"),
        growth_percent=Decimal("10"),
        periods=["2026-07", "2026-08", "2026-09"],
    )

    lines_1 = list(version_1.lines.order_by("period").values_list("amount", flat=True))
    lines_2 = list(version_2.lines.order_by("period").values_list("amount", flat=True))
    assert lines_1 == lines_2 == [Decimal("1000.00"), Decimal("1100.00"), Decimal("1210.00")]  # deterministic
    assert version_1.assumptions["growth_percent"] == "10"  # assumptions exported with the result
    assert version_2.version == version_1.version + 1


@pytest.mark.django_db
def test_scenario_comparison_has_no_side_effects() -> None:
    org = _make_org("scenario")
    forecast = Forecast.objects.create(organization=org, label="Simu")

    results = compare_scenarios(
        base_amount=Decimal("1000.00"),
        periods=["p1", "p2"],
        scenarios={"prudent": Decimal("0"), "central": Decimal("10"), "optimiste": Decimal("25")},
    )

    assert results["prudent"] == Decimal("2000.00")
    assert results["central"] == Decimal("2100.00")
    assert results["optimiste"] == Decimal("2250.00")
    assert forecast.versions.count() == 0  # nothing booked anywhere


@pytest.mark.django_db
def test_cash_projection_sources_each_flow_and_alerts() -> None:
    org = _make_org("cash")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client Cash")
    invoice_1 = _issued_invoice(org, party, unit_price="1000.00")  # 1200 incl tax
    invoice_2 = _issued_invoice(org, party, unit_price="2000.00")  # 2400 incl tax

    payment = register_payment(
        organization_id=str(org.id),
        amount=Decimal("1200.00"),
        method="transfer",
        idempotency_key="cash-1",
    )
    allocate_payment(payment_id=str(payment.id), invoice_id=str(invoice_1.id), amount=Decimal("1200.00"))

    flows = expected_inflows(organization_id=str(org.id), as_of=date.today(), horizon_days=60)
    assert len(flows) == 1  # paid invoice excluded: no double counting
    assert flows[0]["amount"] == Decimal("2400.00")
    assert flows[0]["source"] == invoice_2.number  # every flow traceable to its source
    assert flows[0]["certainty"] == "certain"

    alerts = low_point_alerts(
        opening_balance=Decimal("-100.00"),
        flows=flows,
        threshold=Decimal("0.00"),
    )
    assert alerts[0]["balance"] == Decimal("-100.00")

    no_flows = expected_inflows(organization_id=str(org.id), as_of=date.today(), horizon_days=1)
    assert no_flows == [] or all(f["date"] <= date.today() + timedelta(days=1) for f in no_flows)


@pytest.mark.django_db
def test_margin_reconciles_with_invoice_source() -> None:
    org = _make_org("margin")
    party_a = create_party(organization_id=str(org.id), kind="organization", display_name="Client A")
    party_b = create_party(organization_id=str(org.id), kind="organization", display_name="Client B")
    _issued_invoice(org, party_a, unit_price="1000.00")
    _issued_invoice(org, party_b, unit_price="3000.00")

    report = margin_by_party(
        organization_id=str(org.id),
        direct_costs={str(party_a.id): Decimal("400.00"), str(party_b.id): Decimal("1000.00")},
    )

    assert report["reconciled"] is True  # allocations total equals the invoice source
    assert report["total_revenue"] == Decimal("4000.00")
    margins = {row["party"]: row["margin"] for row in report["rows"]}
    assert margins == {"Client A": Decimal("600.00"), "Client B": Decimal("2000.00")}


@pytest.mark.django_db
def test_sales_funnel_reconciliation_and_loss_reasons() -> None:
    org = _make_org("funnel")
    lead_won = Lead.objects.create(organization=org, display_name="Prospect Gagné")
    lead_lost = Lead.objects.create(organization=org, display_name="Prospect Perdu")

    convert_lead_to_opportunity(lead_id=str(lead_won.id), label="Deal A")
    opportunity_lost = convert_lead_to_opportunity(lead_id=str(lead_lost.id), label="Deal B")
    lose_opportunity(opportunity_id=str(opportunity_lost.id), reason="Prix trop élevé")

    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client Funnel")
    _issued_invoice(org, party)

    funnel = sales_funnel(organization_id=str(org.id))
    assert funnel["leads"] == 2
    assert funnel["opportunities"] == 2
    assert funnel["lost"] == 1
    assert funnel["quotes"] == 1
    assert funnel["orders"] == 1
    assert funnel["invoices"] == 1

    reasons = loss_reasons(organization_id=str(org.id))
    assert reasons == [{"loss_reason": "Prix trop élevé", "count": 1}]


@pytest.mark.django_db
def test_report_runs_are_permission_checked_and_reproducible() -> None:
    org = _make_org("report")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client Report")
    _issued_invoice(org, party, unit_price="500.00")
    _issued_invoice(org, party, unit_price="5000.00")

    with pytest.raises(ValueError, match="Unknown dataset"):
        create_report(organization_id=str(org.id), code="bad", label="Bad", dataset_key="secret_table")

    report = create_report(
        organization_id=str(org.id),
        code="invoices",
        label="Factures émises",
        dataset_key="issued_invoices",
    )

    user = get_user_model().objects.create_user(username="report_user", password="StrongPass123!")
    membership = user.memberships.create(organization=org)

    with pytest.raises(PermissionError, match="denied"):
        run_report(report_id=str(report.id), membership_id=str(membership.id))  # unauthorized blocked

    Role.objects.create(code="report-reader", label="Reader", can_read=True)
    assign_role(membership_id=str(membership.id), role_code="report-reader")

    run_1, rows_1 = run_report(
        report_id=str(report.id),
        membership_id=str(membership.id),
        parameters={"min_total": "1000"},
    )
    run_2, rows_2 = run_report(
        report_id=str(report.id),
        membership_id=str(membership.id),
        parameters={"min_total": "1000"},
    )

    assert rows_1 == rows_2  # reproducible with identical parameters
    assert run_1.row_count == 1  # only the 6000.00 invoice passes the filter
    assert run_1.parameters == {"min_total": "1000"}  # parameters stored with the run
