"""Lot 8 (C14 e-invoicing) and foundation completions (F06-F12): acceptance tests."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from modular_brix.finance.einvoicing.models import ProviderConfiguration
from modular_brix.finance.einvoicing.services import (
    prepare_electronic_invoice,
    register_adapter,
    sync_provider_status,
    transmit,
)
from modular_brix.foundation.configuration.models import CustomFieldDefinition
from modular_brix.foundation.configuration.services import (
    missing_required_custom_fields,
    set_custom_field,
)
from modular_brix.foundation.data_transfer.models import ImportMapping
from modular_brix.foundation.data_transfer.services import (
    apply_import_mapping,
    seal_export,
    verify_export_seal,
)
from modular_brix.foundation.documents.services import (
    add_document_version,
    clear_file_scanners,
    create_document,
    register_file_scanner,
    sign_document_version,
)
from modular_brix.foundation.notifications.models import NotificationPreference, NotificationSuppression
from modular_brix.foundation.notifications.services import queue_notification
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.reference_data.models import BusinessCalendar, Holiday
from modular_brix.foundation.reference_data.services import add_business_days, is_business_day

from test_invoice_compliance import _draft_invoice, _issue_compliant, _make_org


def _org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"fnd-{suffix}",
        legal_name=f"Fnd {suffix}",
        legal_identifier=f"FND-{suffix}",
        country_code="FR",
    )


# --- C14 e-invoicing ------------------------------------------------------


@pytest.mark.django_db
def test_einvoice_payload_frozen_transmission_idempotent_adapter_swappable() -> None:
    from modular_brix.management.parties.services import create_party

    org = _make_org("c14")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client E")
    invoice = _issue_compliant(_draft_invoice(org, party))
    ProviderConfiguration.objects.create(organization=org, adapter_code="reference")

    electronic = prepare_electronic_invoice(invoice_id=str(invoice.id))
    assert prepare_electronic_invoice(invoice_id=str(invoice.id)).id == electronic.id
    assert electronic.payload["number"] == invoice.number
    electronic.payload = {"forgé": True}
    with pytest.raises(ValueError, match="frozen"):
        electronic.save()

    first = transmit(electronic_invoice_id=str(electronic.id), idempotency_key="send-1")
    replay = transmit(electronic_invoice_id=str(electronic.id), idempotency_key="send-1")
    assert replay.id == first.id  # no double emission
    assert first.status == "accepted"

    # Swapping the platform adapter never touches C01 nor the frozen payload.
    register_adapter("other", lambda payload: ("pending", "queued upstream"))
    ProviderConfiguration.objects.filter(organization=org).update(adapter_code="other")
    second = transmit(electronic_invoice_id=str(electronic.id), idempotency_key="send-2")
    assert second.status == "pending" and second.adapter_code == "other"

    _, diverged = sync_provider_status(transmission_id=str(second.id), provider_status="accepted")
    assert diverged is True  # local/provider gap detected


@pytest.mark.django_db
def test_einvoice_refuses_incomplete_mentions() -> None:
    from modular_brix.finance.billing.services import issue_invoice
    from modular_brix.management.parties.services import create_party

    org = _make_org("c14-gap", with_profiles=False)
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client G")
    invoice = issue_invoice(invoice_id=str(_draft_invoice(org, party).id))
    with pytest.raises(ValueError, match="missing mandatory mentions"):
        prepare_electronic_invoice(invoice_id=str(invoice.id))


# --- F06 signatures and file acceptance -----------------------------------


@pytest.mark.django_db
def test_document_signature_immutable_and_file_controls() -> None:
    org = _org("f06")
    document = create_document(
        organization_id=str(org.id),
        category_code="contrats",
        category_label="Contrats",
        object_type="contract",
        object_id="c-1",
        is_regulatory=False,
    )
    with pytest.raises(ValueError, match="not accepted"):
        add_document_version(
            document_id=str(document.id),
            file_name="payload.exe",
            content_sha256="a" * 64,
            byte_size=10,
            created_by_user_id=None,
        )
    register_file_scanner(lambda name, sha: "infected" not in name)
    try:
        with pytest.raises(ValueError, match="rejected by a content scanner"):
            add_document_version(
                document_id=str(document.id),
                file_name="infected.pdf",
                content_sha256="b" * 64,
                byte_size=10,
                created_by_user_id=None,
            )
        version = add_document_version(
            document_id=str(document.id),
            file_name="contrat.pdf",
            content_sha256="c" * 64,
            byte_size=10,
            created_by_user_id=None,
        )
    finally:
        clear_file_scanners()

    signature = sign_document_version(version_id=str(version.id), signer_name="Mme Dupont")
    assert signature.signed_content_sha256 == version.content_sha256
    signature.signer_name = "Autre"
    with pytest.raises(ValueError, match="never be modified"):
        signature.save()
    with pytest.raises(ValueError, match="never be modified"):
        signature.delete()


# --- F07 suppression and preferences --------------------------------------


@pytest.mark.django_db
def test_suppressed_or_opted_out_recipient_never_queued() -> None:
    org = _org("f07")
    user = get_user_model().objects.create_user(username="f07_user", password="StrongPass123!")
    user.memberships.create(organization=org)

    NotificationSuppression.objects.create(
        organization=org, recipient_user=user, channel="email", reason="hard bounce"
    )
    with pytest.raises(ValueError, match="suppression list"):
        queue_notification(
            organization_id=str(org.id),
            recipient_user_id=user.id,
            channel="email",
            subject="Relance",
            body="...",
            idempotency_key="f07-1",
        )
    # Other channels stay open.
    queue_notification(
        organization_id=str(org.id),
        recipient_user_id=user.id,
        channel="in_app",
        subject="Relance",
        body="...",
        idempotency_key="f07-2",
    )
    NotificationPreference.objects.create(organization=org, user=user, channel="sms", is_enabled=False)
    with pytest.raises(ValueError, match="disabled this notification channel"):
        queue_notification(
            organization_id=str(org.id),
            recipient_user_id=user.id,
            channel="sms",
            subject="Relance",
            body="...",
            idempotency_key="f07-3",
        )


# --- F08 custom fields ----------------------------------------------------


@pytest.mark.django_db
def test_custom_fields_typed_and_required_check() -> None:
    org = _org("f08")
    number_field = CustomFieldDefinition.objects.create(
        organization=org, model_label="management_parties.Party", key="effectif", kind="number"
    )
    choice_field = CustomFieldDefinition.objects.create(
        organization=org,
        model_label="management_parties.Party",
        key="segment",
        kind="choice",
        is_required=True,
        choices=["PME", "ETI", "GE"],
    )

    with pytest.raises(ValueError, match="expects a number"):
        set_custom_field(definition_id=str(number_field.id), object_id="p-1", value="douze")
    set_custom_field(definition_id=str(number_field.id), object_id="p-1", value=12)
    with pytest.raises(ValueError, match="expects one of"):
        set_custom_field(definition_id=str(choice_field.id), object_id="p-1", value="TPE")

    assert missing_required_custom_fields(
        organization_id=str(org.id), model_label="management_parties.Party", object_id="p-1"
    ) == ["segment"]
    set_custom_field(definition_id=str(choice_field.id), object_id="p-1", value="PME")
    assert (
        missing_required_custom_fields(
            organization_id=str(org.id), model_label="management_parties.Party", object_id="p-1"
        )
        == []
    )


# --- F10 calendars --------------------------------------------------------


@pytest.mark.django_db
def test_business_days_skip_weekends_and_holidays() -> None:
    org = _org("f10")
    calendar = BusinessCalendar.objects.create(organization=org)
    Holiday.objects.create(calendar=calendar, day=date(2026, 7, 14), label="Fête nationale")

    assert is_business_day(organization_id=str(org.id), day=date(2026, 7, 13)) is True
    assert is_business_day(organization_id=str(org.id), day=date(2026, 7, 14)) is False
    assert is_business_day(organization_id=str(org.id), day=date(2026, 7, 12)) is False  # Sunday

    # Friday 10 July + 2 business days skips the weekend and the 14th.
    assert add_business_days(organization_id=str(org.id), start=date(2026, 7, 10), days=2) == date(2026, 7, 15)


# --- F11 import mappings and export seals ---------------------------------


@pytest.mark.django_db
def test_import_mapping_and_export_seal() -> None:
    org = _org("f11")
    mapping = ImportMapping.objects.create(
        organization=org,
        code="clients-v1",
        field_map={"Nom": "display_name", "Courriel": "email"},
    )
    mapped = apply_import_mapping(
        mapping_id=str(mapping.id), row={"Nom": "Durand SA", "Courriel": "x@y.fr", "Inutile": "?"}
    )
    assert mapped == {"display_name": "Durand SA", "email": "x@y.fr"}

    seal = seal_export(payload="ligne1;ligne2", secret="s3cret")
    assert verify_export_seal(payload="ligne1;ligne2", secret="s3cret", seal=seal) is True
    assert verify_export_seal(payload="ligne1;ligne2-altérée", secret="s3cret", seal=seal) is False


# --- F12 partials ---------------------------------------------------------


@pytest.mark.django_db
def test_f12_partials_render() -> None:
    from django.template.loader import render_to_string

    html = render_to_string(
        "ui/partials/list_results.html",
        {"rows": [{"cells": ["Durand", "Paris"]}], "columns": 2},
    )
    assert "Durand" in html and 'id="list-results"' in html
    empty = render_to_string("ui/partials/list_results.html", {"rows": [], "columns": 2})
    assert "Aucun résultat" in empty
