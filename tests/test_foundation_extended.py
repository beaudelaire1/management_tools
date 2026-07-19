import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from modular_brix.foundation.accounts.services import (
    accept_invitation,
    invite_user,
    is_account_locked,
    record_session,
    register_failed_authentication,
    reset_authentication_failures,
    revoke_all_sessions,
)
from modular_brix.foundation.organizations.models import BrandSettings, Organization
from modular_brix.foundation.organizations.services import (
    archive_organization,
    create_organization_with_default_establishment,
)
from modular_brix.foundation.permissions.models import PolicyDecisionLog, Role
from modular_brix.foundation.permissions.policies import has_action_permission
from modular_brix.foundation.permissions.services import assign_role, delegate_role


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"EXT-{suffix}",
        country_code="FR",
    )


def _make_membership(org, username: str):
    invitation = invite_user(organization_id=str(org.id), email=f"{username}@example.test")
    return accept_invitation(token=invitation.token, username=username, password="StrongPass123!")


@pytest.mark.django_db
def test_archive_organization_keeps_history() -> None:
    org = _make_org("archive")
    archived = archive_organization(organization_id=str(org.id))

    assert archived.is_active is False
    assert Organization.objects.filter(id=org.id).exists()  # never deleted
    assert archived.establishments.filter(is_active=True).count() == 0


@pytest.mark.django_db
def test_brand_settings_attached_to_organization() -> None:
    org = _make_org("brand")
    BrandSettings.objects.create(organization=org, display_name="Client Brand")
    assert org.brand_settings.display_name == "Client Brand"


@pytest.mark.django_db
def test_session_revocation() -> None:
    org = _make_org("sessions")
    membership = _make_membership(org, "sess_user")
    record_session(user_id=membership.user_id, session_key="s1")
    record_session(user_id=membership.user_id, session_key="s2")

    revoked = revoke_all_sessions(user_id=membership.user_id)
    assert revoked == 2
    assert revoke_all_sessions(user_id=membership.user_id) == 0  # idempotent


@pytest.mark.django_db
def test_progressive_lockout() -> None:
    user = get_user_model().objects.create_user(username="lock_user", password="StrongPass123!")

    for _ in range(4):
        register_failed_authentication(user_id=user.id)
    assert is_account_locked(user_id=user.id) is False

    register_failed_authentication(user_id=user.id)  # 5th attempt reaches threshold
    assert is_account_locked(user_id=user.id) is True

    reset_authentication_failures(user_id=user.id)
    assert is_account_locked(user_id=user.id) is False


@pytest.mark.django_db
def test_self_elevation_is_blocked() -> None:
    org = _make_org("self-elev")
    membership = _make_membership(org, "self_user")
    Role.objects.create(code="admin-role", label="Admin", can_validate=True)

    with pytest.raises(ValueError, match="Self-elevation"):
        assign_role(
            membership_id=str(membership.id),
            role_code="admin-role",
            actor_membership_id=str(membership.id),
        )


@pytest.mark.django_db
def test_delegation_grants_temporary_permission_and_decisions_are_logged() -> None:
    org = _make_org("delegation")
    manager = _make_membership(org, "manager_user")
    substitute = _make_membership(org, "substitute_user")
    role = Role.objects.create(code="validator", label="Validator", can_validate=True)
    assign_role(membership_id=str(manager.id), role_code=role.code)

    assert has_action_permission(membership_id=str(substitute.id), action="validate") is False

    with pytest.raises(ValueError, match="Self-delegation"):
        delegate_role(
            role_code=role.code,
            from_membership_id=str(manager.id),
            to_membership_id=str(manager.id),
            starts_at=timezone.now(),
            ends_at=timezone.now() + timezone.timedelta(days=1),
        )

    delegate_role(
        role_code=role.code,
        from_membership_id=str(manager.id),
        to_membership_id=str(substitute.id),
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(days=1),
    )
    assert has_action_permission(membership_id=str(substitute.id), action="validate") is True

    reasons = set(
        PolicyDecisionLog.objects.filter(membership_id=substitute.id, action="validate").values_list(
            "reason", flat=True
        )
    )
    assert reasons == {"no_grant", "delegation"}
