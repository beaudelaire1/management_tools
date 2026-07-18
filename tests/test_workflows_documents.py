import pytest
from django.contrib.auth import get_user_model

from modular_brix.foundation.documents.policies import can_access_document
from modular_brix.foundation.documents.selectors import list_document_versions
from modular_brix.foundation.documents.services import add_document_version, create_document, revoke_document_access
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.workflows.services import (
    apply_transition,
    create_workflow_definition,
    create_workflow_state,
    create_workflow_transition,
    start_workflow_instance,
)


@pytest.mark.django_db
def test_workflow_illegal_transition_is_blocked() -> None:
    org = create_organization_with_default_establishment(
        slug="org-wf-a",
        legal_name="WF A",
        legal_identifier="WF-A-1",
        country_code="FR",
    )
    definition = create_workflow_definition(organization_id=str(org.id), code="invoice-approval")
    state_draft = create_workflow_state(
        definition_id=str(definition.id),
        code="draft",
        label="Draft",
        is_initial=True,
    )
    state_validated = create_workflow_state(
        definition_id=str(definition.id),
        code="validated",
        label="Validated",
    )
    state_rejected = create_workflow_state(
        definition_id=str(definition.id),
        code="rejected",
        label="Rejected",
        is_terminal=True,
    )
    create_workflow_transition(
        definition_id=str(definition.id),
        code="validate",
        source_state_id=str(state_draft.id),
        target_state_id=str(state_validated.id),
    )
    create_workflow_transition(
        definition_id=str(definition.id),
        code="reject",
        source_state_id=str(state_validated.id),
        target_state_id=str(state_rejected.id),
    )

    instance = start_workflow_instance(
        organization_id=str(org.id),
        definition_id=str(definition.id),
        object_type="invoice",
        object_id="INV-100",
        requester_user_id=None,
    )

    with pytest.raises(ValueError, match="Illegal transition"):
        apply_transition(
            instance_id=str(instance.id),
            transition_code="reject",
            actor_user_id=None,
            idempotency_key="k-1",
        )


@pytest.mark.django_db
def test_workflow_separate_approver_and_idempotency() -> None:
    org = create_organization_with_default_establishment(
        slug="org-wf-b",
        legal_name="WF B",
        legal_identifier="WF-B-1",
        country_code="FR",
    )
    user_model = get_user_model()
    requester = user_model.objects.create_user(username="requester", email="requester@test.local", password="StrongPass123!")
    approver = user_model.objects.create_user(username="approver", email="approver@test.local", password="StrongPass123!")

    definition = create_workflow_definition(organization_id=str(org.id), code="quote-approval")
    state_pending = create_workflow_state(
        definition_id=str(definition.id),
        code="pending",
        label="Pending",
        is_initial=True,
    )
    state_approved = create_workflow_state(
        definition_id=str(definition.id),
        code="approved",
        label="Approved",
        is_terminal=True,
    )
    create_workflow_transition(
        definition_id=str(definition.id),
        code="approve",
        source_state_id=str(state_pending.id),
        target_state_id=str(state_approved.id),
        require_separate_approver=True,
    )

    instance = start_workflow_instance(
        organization_id=str(org.id),
        definition_id=str(definition.id),
        object_type="quote",
        object_id="Q-1",
        requester_user_id=requester.id,
    )

    with pytest.raises(ValueError, match="Requester cannot approve"):
        apply_transition(
            instance_id=str(instance.id),
            transition_code="approve",
            actor_user_id=requester.id,
            idempotency_key="same-key",
        )

    decision_1 = apply_transition(
        instance_id=str(instance.id),
        transition_code="approve",
        actor_user_id=approver.id,
        idempotency_key="idempo-1",
    )
    decision_2 = apply_transition(
        instance_id=str(instance.id),
        transition_code="approve",
        actor_user_id=approver.id,
        idempotency_key="idempo-1",
    )

    assert decision_1.id == decision_2.id


@pytest.mark.django_db
def test_document_versioning_and_access_isolation() -> None:
    org_a = create_organization_with_default_establishment(
        slug="org-doc-a",
        legal_name="Doc A",
        legal_identifier="DOC-A-1",
        country_code="FR",
    )
    org_b = create_organization_with_default_establishment(
        slug="org-doc-b",
        legal_name="Doc B",
        legal_identifier="DOC-B-1",
        country_code="FR",
    )

    document = create_document(
        organization_id=str(org_a.id),
        category_code="invoice",
        category_label="Invoice",
        object_type="invoice",
        object_id="INV-200",
        is_regulatory=True,
    )
    add_document_version(
        document_id=str(document.id),
        file_name="inv-200-v1.pdf",
        content_sha256="a" * 64,
        byte_size=100,
        created_by_user_id=None,
    )
    add_document_version(
        document_id=str(document.id),
        file_name="inv-200-v2.pdf",
        content_sha256="b" * 64,
        byte_size=120,
        created_by_user_id=None,
        allow_regulatory_replacement=True,
    )

    versions = list(list_document_versions(document_id=str(document.id)))
    assert [v.version_number for v in versions] == [1, 2]
    assert versions[0].is_current is False
    assert versions[1].is_current is True

    assert can_access_document(actor_organization_id=str(org_a.id), document=document) is True
    assert can_access_document(actor_organization_id=str(org_b.id), document=document) is False

    revoke_document_access(document_id=str(document.id))
    document.refresh_from_db()
    assert can_access_document(actor_organization_id=str(org_a.id), document=document) is False
