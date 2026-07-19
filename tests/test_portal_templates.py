from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import reverse

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.payments.models import Payment, PaymentAllocation
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import Role
from modular_brix.foundation.permissions.services import assign_role
from modular_brix.management.crm.models import Lead
from modular_brix.management.parties.models import Party
from modular_brix.management.parties.services import create_party
from modular_brix.management.sales.models import Quote, SalesOrder
from modular_brix.portal.resources import RESOURCES
from modular_brix.portal.configuration import load_portal_configuration


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"portal-{suffix}",
        legal_name=f"Portail {suffix}",
        legal_identifier=f"PORTAL-{suffix}",
        country_code="FR",
    )


def _make_user_with_role(
    organization,
    suffix: str,
    *,
    can_read: bool = True,
    can_create: bool = True,
    can_validate: bool = True,
):
    user = get_user_model().objects.create_user(
        username=f"portal_{suffix}",
        email=f"portal-{suffix}@example.test",
        password="StrongPass123!",
    )
    membership = user.memberships.create(organization=organization)
    role = Role.objects.create(
        code=f"portal-{suffix}",
        label=f"Portail {suffix}",
        can_read=can_read,
        can_create=can_create,
        can_validate=can_validate,
    )
    assign_role(
        membership_id=str(membership.id),
        role_code=role.code,
        trusted_system=True,
    )
    return user


@pytest.mark.django_db
def test_login_and_organization_picker_templates(client) -> None:
    login_response = client.get(reverse("login"))
    assert login_response.status_code == 200
    assert "Connexion" in login_response.content.decode()
    assert 'name="username"' in login_response.content.decode()

    assert client.get(reverse("portal:organization-picker")).status_code == 302

    first = _make_org("picker-a")
    second = _make_org("picker-b")
    user = _make_user_with_role(first, "picker")
    user.memberships.create(organization=second)
    client.force_login(user)

    response = client.get(reverse("portal:organization-picker"))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Choisir une organisation" in content
    assert first.legal_name in content
    assert second.legal_name in content


@pytest.mark.django_db
def test_home_and_resource_list_are_tenant_scoped(client) -> None:
    first = _make_org("tenant-a")
    second = _make_org("tenant-b")
    user = _make_user_with_role(first, "tenant")
    create_party(
        organization_id=str(first.id),
        kind="organization",
        display_name="Client visible",
    )
    create_party(
        organization_id=str(second.id),
        kind="organization",
        display_name="Client secret",
    )
    client.force_login(user)

    home = client.get(reverse("portal:home", args=[first.slug]))
    assert home.status_code == 200
    assert "Vue d’ensemble" in home.content.decode()
    assert "Client secret" not in home.content.decode()

    listing = client.get(
        reverse("portal:resource-list", args=[first.slug, "parties"]),
        {"q": "visible"},
    )
    content = listing.content.decode()
    assert listing.status_code == 200
    assert "Client visible" in content
    assert "Client secret" not in content

    assert client.get(reverse("portal:home", args=[second.slug])).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("resource_key", [resource.key for resource in RESOURCES])
def test_every_portal_resource_has_a_working_list_template(client, resource_key: str) -> None:
    organization = _make_org(f"list-{resource_key}")
    user = _make_user_with_role(organization, f"list-{resource_key}")
    client.force_login(user)

    response = client.get(reverse("portal:resource-list", args=[organization.slug, resource_key]))

    assert response.status_code == 200
    assert response.context["resource"].key == resource_key
    assert "Aucun résultat" in response.content.decode()


@pytest.mark.django_db
@override_settings(
    MODULAR_BRIX_PORTAL={
        "theme": {"brand": "#3156a3", "sidebar_width": "280px"},
        "layout": {"navigation": "right", "header": "static", "density": "compact"},
    }
)
def test_portal_theme_and_layout_are_configurable_without_template_changes(client) -> None:
    organization = _make_org("custom-theme")
    user = _make_user_with_role(organization, "custom-theme")
    client.force_login(user)

    response = client.get(reverse("portal:home", args=[organization.slug]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "--brand: #3156a3" in content
    assert "--sidebar-width: 280px" in content
    assert "layout-nav-right header-static density-compact" in content


@override_settings(MODULAR_BRIX_PORTAL={"theme": {"brand": "url(javascript:alert(1))"}})
def test_portal_rejects_unsafe_theme_tokens() -> None:
    with pytest.raises(ImproperlyConfigured, match="six-digit hexadecimal"):
        load_portal_configuration()


@pytest.mark.django_db
@override_settings(MODULAR_BRIX_PORTAL={"enabled_bricks": ["management_parties"]})
def test_portal_can_enable_only_selected_bricks(client) -> None:
    organization = _make_org("selected-bricks")
    user = _make_user_with_role(organization, "selected-bricks")
    client.force_login(user)

    parties = client.get(reverse("portal:resource-list", args=[organization.slug, "parties"]))
    quotes = client.get(reverse("portal:resource-list", args=[organization.slug, "quotes"]))

    assert parties.status_code == 200
    assert quotes.status_code == 404
    assert "Devis" not in parties.content.decode()


@pytest.mark.django_db
def test_resource_details_cannot_cross_organization_boundaries(client) -> None:
    first = _make_org("detail-a")
    second = _make_org("detail-b")
    user = _make_user_with_role(first, "detail")
    visible = create_party(
        organization_id=str(first.id),
        kind="organization",
        display_name="Tiers autorisé",
    )
    hidden = create_party(
        organization_id=str(second.id),
        kind="organization",
        display_name="Tiers interdit",
    )
    client.force_login(user)

    visible_response = client.get(
        reverse("portal:resource-detail", args=[first.slug, "parties", visible.pk])
    )
    hidden_response = client.get(
        reverse("portal:resource-detail", args=[first.slug, "parties", hidden.pk])
    )

    assert visible_response.status_code == 200
    assert "Tiers autorisé" in visible_response.content.decode()
    assert hidden_response.status_code == 404


@pytest.mark.django_db
def test_create_forms_write_to_the_selected_organization_and_enforce_permissions(client) -> None:
    organization = _make_org("forms")
    editor = _make_user_with_role(organization, "forms-editor")
    client.force_login(editor)

    party_response = client.post(
        reverse("portal:party-create", args=[organization.slug]),
        {"kind": "organization", "display_name": "Nouveau client", "email": "client@example.test"},
    )
    lead_response = client.post(
        reverse("portal:lead-create", args=[organization.slug]),
        {"display_name": "Nouveau prospect", "email": "prospect@example.test"},
    )

    assert party_response.status_code == 302
    assert lead_response.status_code == 302
    assert Party.objects.filter(organization=organization, display_name="Nouveau client").exists()
    assert Lead.objects.filter(organization=organization, display_name="Nouveau prospect").exists()

    reader = _make_user_with_role(
        organization,
        "forms-reader",
        can_create=False,
        can_validate=False,
    )
    client.force_login(reader)
    reader_listing = client.get(
        reverse("portal:resource-list", args=[organization.slug, "parties"])
    )
    assert reverse("portal:party-create", args=[organization.slug]) not in reader_listing.content.decode()

    denied = client.post(
        reverse("portal:party-create", args=[organization.slug]),
        {"kind": "organization", "display_name": "Création interdite"},
    )
    assert denied.status_code == 403
    assert not Party.objects.filter(display_name="Création interdite").exists()


@pytest.mark.django_db
def test_quote_to_cash_portal_flow_uses_domain_services(client) -> None:
    organization = _make_org("quote-to-cash")
    user = _make_user_with_role(organization, "quote-to-cash")
    party = create_party(
        organization_id=str(organization.id),
        kind="organization",
        display_name="Client parcours complet",
    )
    client.force_login(user)

    response = client.post(
        reverse("portal:quote-create", args=[organization.slug]),
        {"party": party.pk, "currency": "eur"},
    )
    assert response.status_code == 302
    quote = Quote.objects.get(organization=organization)
    assert quote.currency == "EUR"

    response = client.post(
        reverse("portal:quote-line-create", args=[organization.slug, quote.pk]),
        {
            "description": "Accompagnement",
            "quantity": "1",
            "unit_price": "100.00",
            "tax_rate": "20",
        },
    )
    assert response.status_code == 302
    assert quote.lines.count() == 1

    assert client.post(reverse("portal:quote-send", args=[organization.slug, quote.pk])).status_code == 302
    quote.refresh_from_db()
    assert quote.status == "sent"
    assert quote.total_incl_tax == Decimal("120.00")

    response = client.post(
        reverse("portal:quote-accept", args=[organization.slug, quote.pk]),
        {"acceptance_proof": "Signature électronique REF-42"},
    )
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.status == "accepted"

    assert client.post(reverse("portal:quote-convert", args=[organization.slug, quote.pk])).status_code == 302
    order = SalesOrder.objects.get(quote=quote)

    assert client.post(reverse("portal:order-invoice", args=[organization.slug, order.pk])).status_code == 302
    invoice = Invoice.objects.get(sales_order=order)
    assert invoice.status == "draft"

    assert client.post(reverse("portal:invoice-issue", args=[organization.slug, invoice.pk])).status_code == 302
    invoice.refresh_from_db()
    assert invoice.status == "issued"
    assert invoice.total_incl_tax == Decimal("120.00")

    response = client.post(
        reverse("portal:payment-create", args=[organization.slug]),
        {
            "party": party.pk,
            "amount": "120.00",
            "currency": "eur",
            "method": "transfer",
            "provider_reference": "BANK-42",
            "idempotency_key": "portal-bank-event-42",
        },
    )
    assert response.status_code == 302
    payment = Payment.objects.get(organization=organization)

    response = client.post(
        reverse("portal:payment-allocate", args=[organization.slug, payment.pk]),
        {"invoice": invoice.pk, "amount": "120.00"},
    )
    assert response.status_code == 302
    assert PaymentAllocation.objects.filter(payment=payment, invoice=invoice).exists()

    expected_sections = (
        ("quotes", quote.pk, "Lignes du devis"),
        ("orders", order.pk, "Lignes commandées"),
        ("invoices", invoice.pk, "Reste dû"),
        ("payments", payment.pk, "Affectations"),
    )
    for resource_key, pk, expected_text in expected_sections:
        detail = client.get(
            reverse("portal:resource-detail", args=[organization.slug, resource_key, pk])
        )
        assert detail.status_code == 200
        assert expected_text in detail.content.decode()
