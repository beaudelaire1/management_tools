"""Profitability (P08) and sales analytics (P09): read-only projections, reconciled to sources."""

from decimal import Decimal

from django.db.models import Count, Sum

from modular_brix.finance.billing.models import Invoice
from modular_brix.management.crm.models import Lead, Opportunity
from modular_brix.management.sales.models import Quote, SalesOrder


def margin_by_party(*, organization_id: str, direct_costs: dict[str, Decimal]) -> dict:
    """Revenue per party from issued invoices; direct costs are provided per party id.

    The grand total always reconciles with the invoice source (spec P08).
    """
    rows: list[dict] = []
    total_revenue = Decimal("0.00")
    revenue_qs = (
        Invoice.objects.filter(organization_id=organization_id, status="issued")
        .values("party_id", "party__display_name")
        .annotate(revenue=Sum("total_excl_tax"))
    )
    for entry in revenue_qs:
        revenue = entry["revenue"] or Decimal("0.00")
        cost = direct_costs.get(str(entry["party_id"]), Decimal("0.00"))
        rows.append(
            {
                "party": entry["party__display_name"],
                "revenue": revenue,
                "direct_cost": cost,
                "margin": revenue - cost,
            }
        )
        total_revenue += revenue

    source_total = Invoice.objects.filter(organization_id=organization_id, status="issued").aggregate(
        total=Sum("total_excl_tax")
    )["total"] or Decimal("0.00")
    return {"rows": rows, "total_revenue": total_revenue, "reconciled": total_revenue == source_total}


def sales_funnel(*, organization_id: str) -> dict:
    """Reconciliation leads -> opportunities -> quotes -> orders -> invoices (spec P09)."""
    opportunities = Opportunity.objects.filter(organization_id=organization_id)
    return {
        "leads": Lead.objects.filter(organization_id=organization_id).count(),
        "opportunities": opportunities.count(),
        "won": opportunities.filter(status="won").count(),
        "lost": opportunities.filter(status="lost").count(),
        "quotes": Quote.objects.filter(organization_id=organization_id).count(),
        "orders": SalesOrder.objects.filter(organization_id=organization_id).count(),
        "invoices": Invoice.objects.filter(organization_id=organization_id, status="issued").count(),
    }


def loss_reasons(*, organization_id: str) -> list[dict]:
    return list(
        Opportunity.objects.filter(organization_id=organization_id, status="lost")
        .values("loss_reason")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
