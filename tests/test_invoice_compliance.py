"""C01 completion: full mandatory-mention snapshot and regulatory PDF rendering."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from modular_brix.finance.billing.pdf import render_invoice_pdf
from modular_brix.finance.billing.services import (
    VAT_FRANCHISE_MENTION,
    create_invoice_from_order,
    issue_invoice,
    missing_mandatory_mentions,
)
from modular_brix.foundation.organizations.models import Address, FiscalProfile, LegalEntity, LegalProfile
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import Role
from modular_brix.foundation.permissions.services import assign_role
from modular_brix.management.parties.models import PartyIdentifier
from modular_brix.management.parties.services import create_party
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    send_quote,
)

BUYER_ADDRESS = "12 rue des Clients, 69001 Lyon, FR"


def _make_org(suffix: str, *, with_profiles: bool = True, fiscal_regime: str = "reel_normal"):
    org = create_organization_with_default_establishment(
        slug=f"compliance-{suffix}",
        legal_name=f"Compliance {suffix}",
        legal_identifier=f"SIREN-{suffix}",
        country_code="FR",
    )
    if with_profiles:
        LegalEntity.objects.create(organization=org, name=org.legal_name, legal_form="SAS")
        LegalProfile.objects.create(organization=org, share_capital="10 000 EUR", registry_city="Paris")
        FiscalProfile.objects.create(organization=org, vat_number=f"FR00{suffix}", fiscal_regime=fiscal_regime)
        Address.objects.create(
            organization=org,
            address_type="billing",
            line_1="1 avenue du Vendeur",
            postal_code="75002",
            city="Paris",
            country_code="FR",
        )
    return org


def _draft_invoice(org, party, *, quantity="2", unit_price="500.00", tax_rate="20", line_count=1):
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    for position in range(line_count):
        add_quote_line(
            quote_id=str(quote.id),
            description=f"Prestation {position + 1}",
            quantity=Decimal(quantity),
            unit_price=Decimal(unit_price),
            tax_rate=Decimal(tax_rate),
        )
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="preuve")
    order = convert_quote_to_order(quote_id=str(quote.id))
    return create_invoice_from_order(order_id=str(order.id))


def _issue_compliant(invoice, **overrides):
    parameters = {
        "invoice_id": str(invoice.id),
        "buyer_address": BUYER_ADDRESS,
        "late_penalty_rate": Decimal("12.000"),
    }
    parameters.update(overrides)
    return issue_invoice(**parameters)


@pytest.mark.django_db
def test_issuance_freezes_full_mandatory_mention_snapshot() -> None:
    org = _make_org("snapshot")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client SA")
    PartyIdentifier.objects.create(party=party, scheme="vat", value="FR99CLIENT")

    invoice = _issue_compliant(_draft_invoice(org, party))

    assert invoice.seller_legal_identifier == "SIREN-snapshot"
    assert invoice.seller_legal_form == "SAS"
    assert invoice.seller_share_capital == "10 000 EUR"
    assert invoice.seller_registry_city == "Paris"
    assert invoice.seller_vat_number == "FR00snapshot"
    assert invoice.seller_address == "1 avenue du Vendeur, 75002 Paris, FR"
    assert invoice.buyer_address == BUYER_ADDRESS
    assert invoice.buyer_vat_number == "FR99CLIENT"
    assert invoice.late_penalty_rate == Decimal("12.000")
    assert invoice.recovery_indemnity == Decimal("40.00")
    assert invoice.early_discount_terms == "Escompte pour paiement anticipé : néant"
    assert invoice.vat_exemption_mention == ""
    assert missing_mandatory_mentions(invoice) == []


@pytest.mark.django_db
def test_missing_mentions_are_reported_and_block_pdf_rendering() -> None:
    org = _make_org("gaps", with_profiles=False)
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client G")

    invoice = issue_invoice(invoice_id=str(_draft_invoice(org, party).id))

    missing = missing_mandatory_mentions(invoice)
    assert "seller_address" in missing
    assert "buyer_address" in missing
    assert "late_penalty_rate" in missing
    assert "seller_vat_number" in missing
    with pytest.raises(ValueError, match="missing mandatory mentions"):
        render_invoice_pdf(invoice_id=str(invoice.id))


@pytest.mark.django_db
def test_draft_invoice_cannot_be_rendered() -> None:
    org = _make_org("draft")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client D")
    invoice = _draft_invoice(org, party)

    with pytest.raises(ValueError, match="issued invoice"):
        render_invoice_pdf(invoice_id=str(invoice.id))


@pytest.mark.django_db
def test_pdf_contains_mandatory_mentions_and_is_deterministic() -> None:
    org = _make_org("pdf")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client P")
    invoice = _issue_compliant(_draft_invoice(org, party))

    first = render_invoice_pdf(invoice_id=str(invoice.id))
    second = render_invoice_pdf(invoice_id=str(invoice.id))

    assert first == second  # reproducible financial document
    assert first.startswith(b"%PDF-1.4")
    assert first.rstrip().endswith(b"%%EOF")
    for mention in (
        f"FACTURE {invoice.number}",
        "Compliance pdf",
        "1 avenue du Vendeur, 75002 Paris, FR",
        "Identifiant légal : SIREN-pdf",
        "N° TVA intracommunautaire : FR00pdf",
        "Client P",
        BUYER_ADDRESS,
        "Total TTC : 1200.00 EUR",
        "TVA 20.00 % sur 1000.00 : 200.00 EUR",
        "Pénalités de retard : 12.000 %",  # "(taux annuel)" is backslash-escaped in the stream
        "Indemnité forfaitaire pour frais de recouvrement : 40.00 EUR",
        "Escompte pour paiement anticipé : néant",
    ):
        assert mention.encode("cp1252") in first, mention


@pytest.mark.django_db
def test_vat_franchise_regime_adds_exemption_mention() -> None:
    org = _make_org("franchise", fiscal_regime="franchise_en_base")
    FiscalProfile.objects.filter(organization=org).update(vat_number="")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client F")
    invoice = _issue_compliant(_draft_invoice(org, party, tax_rate="0"))

    assert invoice.vat_exemption_mention == VAT_FRANCHISE_MENTION
    assert missing_mandatory_mentions(invoice) == []  # exemption replaces the VAT number
    pdf = render_invoice_pdf(invoice_id=str(invoice.id))
    assert VAT_FRANCHISE_MENTION.encode("cp1252") in pdf


@pytest.mark.django_db
def test_long_invoice_paginates() -> None:
    org = _make_org("pages")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client L")
    invoice = _issue_compliant(_draft_invoice(org, party, line_count=60))

    pdf = render_invoice_pdf(invoice_id=str(invoice.id))

    assert b"/Count 2" in pdf
    assert b"Prestation 60" in pdf


@pytest.mark.django_db
def test_portal_pdf_download_requires_read_and_streams_pdf() -> None:
    org = _make_org("portal")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client W")
    invoice = _issue_compliant(_draft_invoice(org, party))

    user = get_user_model().objects.create_user(
        username="compliance_portal",
        email="compliance-portal@example.test",
        password="StrongPass123!",
    )
    membership = user.memberships.create(organization=org)
    role = Role.objects.create(code="compliance-portal", label="Compliance", can_read=True)
    assign_role(membership_id=str(membership.id), role_code=role.code, trusted_system=True)

    from django.test import Client

    client = Client()
    url = reverse("portal:invoice-pdf", args=[org.slug, invoice.pk])
    anonymous = client.get(url)
    assert anonymous.status_code == 302  # redirected to login

    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert invoice.number in response["Content-Disposition"]
    assert response.content.startswith(b"%PDF-1.4")


@pytest.mark.django_db
def test_portal_pdf_download_redirects_with_error_when_mentions_incomplete() -> None:
    org = _make_org("portal-gap", with_profiles=False)
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client X")
    invoice = issue_invoice(invoice_id=str(_draft_invoice(org, party).id))

    user = get_user_model().objects.create_user(
        username="compliance_gap",
        email="compliance-gap@example.test",
        password="StrongPass123!",
    )
    membership = user.memberships.create(organization=org)
    role = Role.objects.create(code="compliance-gap", label="Compliance gap", can_read=True)
    assign_role(membership_id=str(membership.id), role_code=role.code, trusted_system=True)

    from django.test import Client

    client = Client()
    client.force_login(user)
    response = client.get(reverse("portal:invoice-pdf", args=[org.slug, invoice.pk]))
    assert response.status_code == 302
    assert response["Location"].endswith(f"/resources/invoices/{invoice.pk}/")
