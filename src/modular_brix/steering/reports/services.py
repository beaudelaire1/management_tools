from collections.abc import Callable

from django.db import transaction

from modular_brix.finance.billing.models import Invoice
from modular_brix.foundation.permissions.policies import has_action_permission

from .models import Report, ReportRun


def _dataset_issued_invoices(organization_id: str, params: dict) -> list[dict]:
    """Read-only dataset: values() queryset, no mutation possible."""
    queryset = Invoice.objects.filter(organization_id=organization_id, status="issued")
    if params.get("min_total") is not None:
        queryset = queryset.filter(total_incl_tax__gte=params["min_total"])
    return list(queryset.order_by("number").values("number", "issue_date", "buyer_name", "total_incl_tax"))


DATASET_REGISTRY: dict[str, Callable[[str, dict], list[dict]]] = {
    "issued_invoices": _dataset_issued_invoices,
}


@transaction.atomic
def create_report(*, organization_id: str, code: str, label: str, dataset_key: str) -> Report:
    if dataset_key not in DATASET_REGISTRY:
        raise ValueError(f"Unknown dataset '{dataset_key}'.")
    return Report.objects.create(
        organization_id=organization_id,
        code=code,
        label=label,
        dataset_key=dataset_key,
    )


@transaction.atomic
def run_report(*, report_id: str, membership_id: str, parameters: dict | None = None) -> tuple[ReportRun, list[dict]]:
    """Permissions inherited from data policies: an unauthorized recipient is blocked (spec P13).

    Each run stores its parameters and timestamp, making the output reproducible.
    """
    report = Report.objects.get(id=report_id)
    if not has_action_permission(membership_id=membership_id, action="read"):
        raise PermissionError("Report execution denied by policy.")
    params = parameters or {}
    rows = DATASET_REGISTRY[report.dataset_key](str(report.organization_id), params)
    run = ReportRun.objects.create(report=report, parameters=params, row_count=len(rows))
    return run, rows
