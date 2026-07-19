from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from modular_brix.foundation.audit.services import record_audit_event

from .models import CarryForward, ClosingRun, ClosingTask


@transaction.atomic
def complete_task(*, task_id: str, evidence: str, prepared_by: str, validated_by: str) -> ClosingTask:
    """Critical tasks require evidence, and preparation is separated from validation."""
    task = ClosingTask.objects.select_for_update().get(id=task_id)
    if task.done_at is not None:
        raise ValueError("This closing task is already done.")
    if task.is_critical and not evidence.strip():
        raise ValueError("A critical closing task requires evidence.")
    if prepared_by.strip() and prepared_by.strip() == validated_by.strip():
        raise ValueError("A closing task cannot be validated by its preparer.")
    task.done_at = timezone.now()
    task.evidence = evidence.strip()
    task.prepared_by = prepared_by.strip()
    task.validated_by = validated_by.strip()
    task.save(update_fields=["done_at", "evidence", "prepared_by", "validated_by"])
    return task


@transaction.atomic
def record_carry_forward(*, run_id: str, rows: list[dict]) -> list[CarryForward]:
    """The opening batch balances or is rejected as a whole (spec C13)."""
    debit = sum(Decimal(str(row.get("debit", 0))) for row in rows)
    credit = sum(Decimal(str(row.get("credit", 0))) for row in rows)
    if debit != credit:
        raise ValueError(f"Carry-forward is unbalanced (debit {debit}, credit {credit}).")
    run = ClosingRun.objects.get(id=run_id)
    return [
        CarryForward.objects.create(
            run=run,
            account_code=row["account_code"],
            debit=Decimal(str(row.get("debit", 0))),
            credit=Decimal(str(row.get("credit", 0))),
        )
        for row in rows
    ]


@transaction.atomic
def close_run(*, run_id: str) -> ClosingRun:
    """Closing is blocked while any critical task is incomplete (spec C13)."""
    run = ClosingRun.objects.select_for_update().get(id=run_id)
    if run.status == "closed":
        raise ValueError("This closing run is already closed.")
    pending_critical = run.tasks.filter(is_critical=True, done_at__isnull=True).count()
    if pending_critical:
        raise ValueError(f"{pending_critical} critical closing task(s) are incomplete; closing is blocked.")
    run.status = "closed"
    run.closed_at = timezone.now()
    run.save(update_fields=["status", "closed_at"])
    fiscal_year = run.fiscal_year
    fiscal_year.status = "closed"
    fiscal_year.save(update_fields=["status"])
    return run


@transaction.atomic
def reopen_run(*, run_id: str, actor_user_id: int | None, reason: str) -> ClosingRun:
    """Reopening is exceptional and always audited (spec C13)."""
    if not reason.strip():
        raise ValueError("Reopening a closed year requires a reason.")
    run = ClosingRun.objects.select_for_update().get(id=run_id)
    if run.status != "closed":
        raise ValueError("Only a closed run can be reopened.")
    run.status = "reopened"
    run.reopened_count += 1
    run.save(update_fields=["status", "reopened_count"])
    fiscal_year = run.fiscal_year
    fiscal_year.status = "open"
    fiscal_year.save(update_fields=["status"])
    record_audit_event(
        organization_id=str(fiscal_year.organization_id),
        actor_user_id=actor_user_id,
        event_type="closing.run.reopened",
        object_type="closing.ClosingRun",
        object_id=str(run.id),
        outcome="success",
        context={"reason": reason.strip()},
    )
    return run
