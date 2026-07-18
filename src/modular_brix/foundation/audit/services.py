from .models import AuditEvent


def record_audit_event(
    *,
    organization_id: str,
    actor_user_id: int | None,
    event_type: str,
    object_type: str,
    object_id: str,
    outcome: str,
    context: dict,
) -> AuditEvent:
    return AuditEvent.objects.create(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        object_type=object_type,
        object_id=object_id,
        outcome=outcome,
        context=context,
    )
