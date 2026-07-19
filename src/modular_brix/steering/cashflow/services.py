"""Cash forecast projections (P07): read-only over billing; every flow is sourced."""

from datetime import date, timedelta
from decimal import Decimal

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.billing.services import invoice_remaining


def expected_inflows(*, organization_id: str, as_of: date, horizon_days: int) -> list[dict]:
    """One entry per open invoice (no double counting), tagged certain, fully sourced."""
    horizon = as_of + timedelta(days=horizon_days)
    flows: list[dict] = []
    for invoice in Invoice.objects.filter(organization_id=organization_id, status="issued").order_by("due_date"):
        remaining = invoice_remaining(invoice)
        if remaining <= 0 or invoice.due_date is None or invoice.due_date > horizon:
            continue
        flows.append(
            {
                "date": max(invoice.due_date, as_of),
                "amount": remaining,
                "certainty": "certain",
                "source": invoice.number,
            }
        )
    return flows


def projected_balance_curve(*, opening_balance: Decimal, flows: list[dict]) -> list[dict]:
    """Running balance ordered by date, deterministic."""
    curve: list[dict] = []
    balance = Decimal(opening_balance)
    for flow in sorted(flows, key=lambda f: f["date"]):
        balance += flow["amount"]
        curve.append({"date": flow["date"], "balance": balance, "source": flow["source"]})
    return curve


def low_point_alerts(*, opening_balance: Decimal, flows: list[dict], threshold: Decimal) -> list[dict]:
    """Configurable alert before the balance crosses the threshold (spec P07)."""
    alerts: list[dict] = []
    if opening_balance < threshold:
        alerts.append({"date": None, "balance": Decimal(opening_balance)})
    for point in projected_balance_curve(opening_balance=opening_balance, flows=flows):
        if point["balance"] < threshold:
            alerts.append({"date": point["date"], "balance": point["balance"]})
    return alerts
