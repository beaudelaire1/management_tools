from django.db import transaction
from django.utils import timezone

from .models import CorrectiveAction, NonConformity

SEVERITIES = ("minor", "major", "critical")
ROOT_CAUSE_REQUIRED_FROM = "major"


@transaction.atomic
def open_non_conformity(
    *, organization_id: str, description: str, severity: str, reference: str = ""
) -> NonConformity:
    if severity not in SEVERITIES:
        raise ValueError(f"Severity must be one of {', '.join(SEVERITIES)}.")
    return NonConformity.objects.create(
        organization_id=organization_id, description=description, severity=severity, reference=reference
    )


@transaction.atomic
def complete_action(*, action_id: str, evidence: str) -> CorrectiveAction:
    action = CorrectiveAction.objects.select_for_update().get(id=action_id)
    if action.done_at is not None:
        raise ValueError("This action is already completed.")
    if not evidence.strip():
        raise ValueError("Completing an action requires evidence.")
    action.done_at = timezone.now()
    action.evidence = evidence.strip()
    action.save(update_fields=["done_at", "evidence"])
    return action


@transaction.atomic
def close_non_conformity(*, non_conformity_id: str, root_cause: str = "") -> NonConformity:
    """Closure is blocked while any action lacks completion evidence; severe cases
    also require a stated root cause (spec P12)."""
    nc = NonConformity.objects.select_for_update().get(id=non_conformity_id)
    if nc.status != "open":
        raise ValueError("This non-conformity is already closed.")
    pending = nc.actions.filter(done_at__isnull=True).count()
    if pending:
        raise ValueError(f"{pending} action(s) are not completed with evidence; closure is blocked.")
    cause = root_cause.strip() or nc.root_cause
    if nc.severity in SEVERITIES[SEVERITIES.index(ROOT_CAUSE_REQUIRED_FROM):] and not cause:
        raise ValueError("A root cause is required to close a major or critical non-conformity.")
    nc.root_cause = cause
    nc.status = "closed"
    nc.closed_at = timezone.now()
    nc.save(update_fields=["root_cause", "status", "closed_at"])
    return nc


@transaction.atomic
def reopen_non_conformity(*, non_conformity_id: str) -> NonConformity:
    """Reopening is possible and traced (spec P12)."""
    nc = NonConformity.objects.select_for_update().get(id=non_conformity_id)
    if nc.status != "closed":
        raise ValueError("Only a closed non-conformity can be reopened.")
    nc.status = "open"
    nc.closed_at = None
    nc.reopened_count += 1
    nc.save(update_fields=["status", "closed_at", "reopened_count"])
    return nc


def overdue_actions(*, organization_id: str) -> list[CorrectiveAction]:
    today = timezone.now().date()
    return list(
        CorrectiveAction.objects.filter(
            non_conformity__organization_id=organization_id, done_at__isnull=True, due_date__lt=today
        )
    )


def resolution_days(nc: NonConformity) -> float | None:
    if nc.closed_at is None:
        return None
    return (nc.closed_at - nc.opened_at).total_seconds() / 86400
