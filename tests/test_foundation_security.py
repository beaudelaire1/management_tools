import pytest
from django.contrib.auth import get_user_model

from modular_brix.foundation.accounts.services import accept_invitation, invite_user
from modular_brix.foundation.audit.models import AuditEvent
from modular_brix.foundation.audit.services import record_audit_event
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import PolicyDecisionLog, Role
from modular_brix.foundation.permissions.policies import has_action_permission
from modular_brix.foundation.permissions.services import assign_role


@pytest.mark.django_db
def test_invitation_acceptance_creates_membership() -> None:
    org = create_organization_with_default_establishment(
        slug="org-invite",
        legal_name="Invite Org",
        legal_identifier="ID-INV-1",
        country_code="FR",
    )
    invitation = invite_user(organization_id=str(org.id), email="user@example.test")

    membership = accept_invitation(token=invitation.token, username="user_invite", password="StrongPass123!")

    assert membership.organization_id == org.id
    assert membership.user.email == "user@example.test"


@pytest.mark.django_db
def test_permissions_default_deny_then_allow_by_role() -> None:
    org = create_organization_with_default_establishment(
        slug="org-perm",
        legal_name="Perm Org",
        legal_identifier="ID-PERM-1",
        country_code="FR",
    )
    user_model = get_user_model()
    user = user_model.objects.create_user(username="perm_user", email="perm@example.test", password="StrongPass123!")
    membership = user.memberships.create(organization=org)

    assert has_action_permission(
        membership_id=str(membership.id), action="export", organization_id=str(org.id)
    ) is False

    Role.objects.create(code="finance-export", label="Finance export", can_export=True)
    assign_role(membership_id=str(membership.id), role_code="finance-export", trusted_system=True)

    assert has_action_permission(
        membership_id=str(membership.id), action="export", organization_id=str(org.id)
    ) is True

    PolicyDecisionLog.objects.all().delete()
    assert has_action_permission(
        membership_id=str(membership.id),
        action="unknown_action",
        organization_id=str(org.id),
    ) is False
    decision = PolicyDecisionLog.objects.get(
        membership=membership,
        target_organization=org,
        action="unknown_action",
    )
    assert decision.allowed is False
    assert decision.reason == "unknown_action"


@pytest.mark.django_db
def test_audit_event_persisted_with_context() -> None:
    org = create_organization_with_default_establishment(
        slug="org-audit",
        legal_name="Audit Org",
        legal_identifier="ID-AUD-1",
        country_code="FR",
    )
    event = record_audit_event(
        organization_id=str(org.id),
        actor_user_id=None,
        event_type="access.denied",
        object_type="invoice",
        object_id="INV-0001",
        outcome="denied",
        context={"reason": "scope_mismatch"},
    )

    fetched = AuditEvent.objects.get(id=event.id)
    assert fetched.outcome == "denied"
    assert fetched.context["reason"] == "scope_mismatch"
