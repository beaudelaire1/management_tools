import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Invitation, Membership


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
