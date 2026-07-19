import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import AccessRestriction, Invitation, Membership, SessionRecord

LOCKOUT_THRESHOLD = 5
LOCKOUT_BASE_MINUTES = 15


@transaction.atomic
def invite_user(*, organization_id: str, email: str, validity_hours: int = 72) -> Invitation:
    expiration = timezone.now() + timezone.timedelta(hours=validity_hours)
    return Invitation.objects.create(
        email=email.strip().lower(),
        organization_id=organization_id,
        token=secrets.token_urlsafe(32),
        expires_at=expiration,
    )


@transaction.atomic
def accept_invitation(*, token: str, username: str, password: str) -> Membership:
    try:
        invitation = (
            Invitation.objects.select_for_update()
            .select_related("organization")
            .get(token=token)
        )
    except Invitation.DoesNotExist:
        # Generic message: identical for unknown, expired, or revoked tokens (anti-enumeration).
        raise ValueError("Invitation is not valid") from None
    now = timezone.now()
    if invitation.revoked_at is not None or invitation.accepted_at is not None or invitation.expires_at <= now:
        raise ValueError("Invitation is not valid")

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=username,
        email=invitation.email,
        password=password,
    )
    membership, _ = Membership.objects.get_or_create(
        user=user,
        organization=invitation.organization,
        defaults={"is_active": True},
    )
    invitation.accepted_at = now
    invitation.save(update_fields=["accepted_at"])
    return membership


def user_has_membership(user_id: int, organization_id: str) -> bool:
    return Membership.objects.filter(user_id=user_id, organization_id=organization_id, is_active=True).exists()


def record_session(*, user_id: int, session_key: str) -> SessionRecord:
    record, _ = SessionRecord.objects.get_or_create(user_id=user_id, session_key=session_key)
    return record


@transaction.atomic
def revoke_all_sessions(*, user_id: int) -> int:
    return SessionRecord.objects.filter(user_id=user_id, revoked_at__isnull=True).update(revoked_at=timezone.now())


@transaction.atomic
def register_failed_authentication(*, user_id: int) -> AccessRestriction:
    """Progressive lockout: each attempt beyond the threshold extends the lock duration."""
    restriction, _ = AccessRestriction.objects.select_for_update().get_or_create(user_id=user_id)
    restriction.failed_attempts += 1
    if restriction.failed_attempts >= LOCKOUT_THRESHOLD:
        overshoot = restriction.failed_attempts - LOCKOUT_THRESHOLD + 1
        restriction.locked_until = timezone.now() + timezone.timedelta(minutes=LOCKOUT_BASE_MINUTES * overshoot)
    restriction.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    return restriction


@transaction.atomic
def reset_authentication_failures(*, user_id: int) -> None:
    AccessRestriction.objects.filter(user_id=user_id).update(failed_attempts=0, locked_until=None)


def is_account_locked(*, user_id: int) -> bool:
    restriction = AccessRestriction.objects.filter(user_id=user_id).first()
    if restriction is None or restriction.locked_until is None:
        return False
    return restriction.locked_until > timezone.now()
