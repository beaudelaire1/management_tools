import threading

import pytest
from django.db import connection

from modular_brix.foundation.audit.models import AuditEvent
from modular_brix.foundation.audit.services import record_audit_event
from modular_brix.foundation.accounts.services import accept_invitation, invite_user, user_has_membership
from modular_brix.foundation.documents.services import add_document_version, create_document
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.sequences.services import allocate_number, format_reference
from modular_brix.foundation.workflows.policies import can_access_workflow_instance
from modular_brix.foundation.workflows.selectors import list_workflow_instances_for_object
from modular_brix.foundation.workflows.services import (
    create_workflow_definition,
    create_workflow_state,
    create_workflow_transition,
    start_workflow_instance,
)


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"ID-{suffix}",
        country_code="FR",
    )


@pytest.mark.django_db
def test_audit_event_is_append_only() -> None:
    org = _make_org("append-only")
    event = record_audit_event(
        organization_id=str(org.id),
        actor_user_id=None,
        event_type="test.event",
        object_type="test",
        object_id="T-1",
        outcome="ok",
        context={},
    )

    event.outcome = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        event.save()

    with pytest.raises(ValueError, match="append-only"):
        event.delete()

    fetched = AuditEvent.objects.get(id=event.id)
    assert fetched.outcome == "ok"


@pytest.mark.django_db
def test_regulatory_document_cannot_be_replaced_silently() -> None:
    org = _make_org("regulatory")
    document = create_document(
        organization_id=str(org.id),
        category_code="invoice",
        category_label="Invoice",
        object_type="invoice",
        object_id="INV-1",
        is_regulatory=True,
    )
    add_document_version(
        document_id=str(document.id),
        file_name="v1.pdf",
        content_sha256="a" * 64,
        byte_size=10,
        created_by_user_id=None,
    )

    with pytest.raises(ValueError, match="cannot be replaced silently"):
        add_document_version(
            document_id=str(document.id),
            file_name="v2.pdf",
            content_sha256="b" * 64,
            byte_size=10,
            created_by_user_id=None,
        )

    version_2 = add_document_version(
        document_id=str(document.id),
        file_name="v2.pdf",
        content_sha256="b" * 64,
        byte_size=10,
        created_by_user_id=None,
        allow_regulatory_replacement=True,
    )
    assert version_2.version_number == 2


@pytest.mark.django_db
def test_invitation_errors_are_generic_anti_enumeration() -> None:
    org = _make_org("anti-enum")

    with pytest.raises(ValueError) as unknown_error:
        accept_invitation(token="unknown-token", username="u1", password="StrongPass123!")

    invitation = invite_user(organization_id=str(org.id), email="x@example.test", validity_hours=0)
    with pytest.raises(ValueError) as expired_error:
        accept_invitation(token=invitation.token, username="u2", password="StrongPass123!")

    assert str(unknown_error.value) == str(expired_error.value)


@pytest.mark.django_db
def test_user_has_membership_scope() -> None:
    org_a = _make_org("member-a")
    org_b = _make_org("member-b")
    invitation = invite_user(organization_id=str(org_a.id), email="m@example.test")
    membership = accept_invitation(token=invitation.token, username="member", password="StrongPass123!")

    assert user_has_membership(membership.user_id, str(org_a.id)) is True
    assert user_has_membership(membership.user_id, str(org_b.id)) is False


@pytest.mark.django_db
def test_sequence_allocation_is_continuous_and_scoped() -> None:
    org_a = _make_org("seq-a")
    org_b = _make_org("seq-b")

    numbers = [allocate_number(organization_id=str(org_a.id), code="invoice", period="2026") for _ in range(5)]
    assert numbers == [1, 2, 3, 4, 5]

    assert allocate_number(organization_id=str(org_b.id), code="invoice", period="2026") == 1
    assert allocate_number(organization_id=str(org_a.id), code="quote", period="2026") == 1
    assert allocate_number(organization_id=str(org_a.id), code="invoice", period="2027") == 1

    assert format_reference(prefix="INV", period="2026", number=5) == "INV-2026-000005"


@pytest.mark.skipif(connection.vendor == "sqlite", reason="Concurrency test requires PostgreSQL (run in CI).")
@pytest.mark.django_db(transaction=True)
def test_sequence_allocation_concurrent_no_duplicates() -> None:
    org = _make_org("seq-concurrent")
    results: list[int] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            number = allocate_number(organization_id=str(org.id), code="invoice", period="2026")
            with lock:
                results.append(number)
        except Exception as exc:  # pragma: no cover - failure path
            with lock:
                errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert sorted(results) == list(range(1, 11))


@pytest.mark.django_db
def test_workflow_definition_frozen_once_instances_exist() -> None:
    org = _make_org("wf-frozen")
    definition = create_workflow_definition(organization_id=str(org.id), code="frozen-flow")
    state = create_workflow_state(
        definition_id=str(definition.id),
        code="start",
        label="Start",
        is_initial=True,
    )
    instance = start_workflow_instance(
        organization_id=str(org.id),
        definition_id=str(definition.id),
        object_type="ticket",
        object_id="T-1",
        requester_user_id=None,
    )

    with pytest.raises(ValueError, match="cannot be modified"):
        create_workflow_state(definition_id=str(definition.id), code="extra", label="Extra")

    with pytest.raises(ValueError, match="cannot be modified"):
        create_workflow_transition(
            definition_id=str(definition.id),
            code="loop",
            source_state_id=str(state.id),
            target_state_id=str(state.id),
        )

    instances = list_workflow_instances_for_object(
        organization_id=str(org.id),
        object_type="ticket",
        object_id="T-1",
    )
    assert list(instances) == [instance]
    assert can_access_workflow_instance(actor_organization_id=str(org.id), instance=instance) is True
    other = _make_org("wf-other")
    assert can_access_workflow_instance(actor_organization_id=str(other.id), instance=instance) is False
