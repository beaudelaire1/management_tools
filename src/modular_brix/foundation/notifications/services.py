import string
from typing import Protocol

from django.db import transaction

from modular_brix.foundation.accounts.models import Membership

from .models import DeliveryAttempt, MessageTemplate, Notification

MAX_DELIVERY_ATTEMPTS = 3


class NotificationChannel(Protocol):
    """Port implemented by concrete adapters (email, SMS, in-app)."""

    def send(self, *, recipient: str, subject: str, body: str) -> None: ...


def _template_variables(template_text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template_text) if name}


@transaction.atomic
def activate_template(*, template_id: str) -> MessageTemplate:
    """A template can only be activated when its declared variables match its placeholders."""
    template = MessageTemplate.objects.select_for_update().get(id=template_id)
    used = _template_variables(template.subject_template) | _template_variables(template.body_template)
    declared = set(template.required_variables)
    if used != declared:
        raise ValueError(f"Template variables mismatch: used={sorted(used)} declared={sorted(declared)}")
    template.is_active = True
    template.save(update_fields=["is_active"])
    return template


def render_template(*, code: str, variables: dict) -> tuple[str, str]:
    template = MessageTemplate.objects.get(code=code, is_active=True)
    missing = set(template.required_variables) - set(variables)
    if missing:
        raise ValueError(f"Missing template variables: {sorted(missing)}")
    return (
        template.subject_template.format(**variables),
        template.body_template.format(**variables),
    )


@transaction.atomic
def queue_notification(
    *,
    organization_id: str,
    recipient_user_id: int | None,
    channel: str,
    subject: str,
    body: str,
    idempotency_key: str,
) -> Notification:
    if recipient_user_id is not None and not Membership.objects.filter(
        user_id=recipient_user_id,
        organization_id=organization_id,
        is_active=True,
    ).exists():
        raise ValueError("A notification recipient must actively belong to the organization.")
    notification, created = Notification.objects.get_or_create(
        organization_id=organization_id,
        idempotency_key=idempotency_key,
        defaults={
            "recipient_user_id": recipient_user_id,
            "channel": channel,
            "subject": subject,
            "body": body,
        },
    )
    if not created:
        replay_payload = {
            "recipient_user_id": recipient_user_id,
            "channel": channel,
            "subject": subject,
            "body": body,
        }
        stored_payload = {
            "recipient_user_id": notification.recipient_user_id,
            "channel": notification.channel,
            "subject": notification.subject,
            "body": notification.body,
        }
        if replay_payload != stored_payload:
            raise ValueError("An idempotency key cannot be reused with a different notification payload.")
    return notification


@transaction.atomic
def deliver_notification(
    *,
    notification_id: str,
    channel_adapter: NotificationChannel,
    recipient: str,
    max_attempts: int = MAX_DELIVERY_ATTEMPTS,
) -> Notification:
    notification = Notification.objects.select_for_update().get(id=notification_id)

    if notification.status == "delivered":
        return notification  # Idempotent redelivery: no double send.

    attempt_count = notification.attempts.count()
    if attempt_count >= max_attempts:
        raise ValueError("Maximum delivery attempts reached; manual retry required.")

    try:
        channel_adapter.send(recipient=recipient, subject=notification.subject, body=notification.body)
    except Exception as exc:
        DeliveryAttempt.objects.create(
            notification=notification,
            attempt_number=attempt_count + 1,
            succeeded=False,
            error=str(exc),
        )
        notification.status = "failed"
        notification.save(update_fields=["status"])
        return notification

    DeliveryAttempt.objects.create(
        notification=notification,
        attempt_number=attempt_count + 1,
        succeeded=True,
    )
    notification.status = "delivered"
    notification.save(update_fields=["status"])
    return notification
