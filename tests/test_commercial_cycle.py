from datetime import date
from decimal import Decimal

import pytest

from modular_brix.management.catalog.models import CatalogItem
from modular_brix.management.catalog.services import resolve_price, set_price
from modular_brix.management.crm.models import Lead
from modular_brix.management.crm.services import convert_lead_to_opportunity, lose_opportunity, win_opportunity
from modular_brix.management.parties.models import Party
from modular_brix.management.parties.services import (
    add_party_role,
    create_party,
    find_duplicate_parties,
    merge_parties,
)
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    record_delivery,
    revise_quote,
    send_quote,
)
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"L2-{suffix}",
        country_code="FR",
    )


@pytest.mark.django_db
def test_party_multi_role_without_duplication() -> None:
    org = _make_org("party-roles")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="ACME SARL")
    add_party_role(party_id=str(party.id), role_type="customer")
    add_party_role(party_id=str(party.id), role_type="supplier")
    add_party_role(party_id=str(party.id), role_type="customer")  # no duplicate

    assert Party.objects.filter(organization=org).count() == 1
    assert party.roles.count() == 2


@pytest.mark.django_db
def test_duplicate_detection_is_accent_and_case_insensitive() -> None:
    org = _make_org("party-dedup")
    create_party(organization_id=str(org.id), kind="organization", display_name="Société Générale")

    duplicates = find_duplicate_parties(organization_id=str(org.id), display_name="societe   GENERALE")
    assert duplicates.count() == 1


@pytest.mark.django_db
def test_merge_keeps_history_and_roles() -> None:
    org = _make_org("party-merge")
    primary = create_party(organization_id=str(org.id), kind="organization", display_name="ACME")
    duplicate = create_party(organization_id=str(org.id), kind="organization", display_name="ACME Corp")
    add_party_role(party_id=str(duplicate.id), role_type="supplier")

    merge_parties(primary_id=str(primary.id), duplicate_id=str(duplicate.id))

    duplicate.refresh_from_db()
    assert duplicate.merged_into_id == primary.id
    assert duplicate.is_active is False
    assert Party.objects.filter(id=duplicate.id).exists()  # history preserved
    assert primary.roles.filter(role_type="supplier").exists()

    with pytest.raises(ValueError, match="already been merged"):
        merge_parties(primary_id=str(primary.id), duplicate_id=str(duplicate.id))


@pytest.mark.django_db
def test_lead_conversion_reuses_party_and_is_idempotent() -> None:
    org = _make_org("crm-convert")
    existing = create_party(organization_id=str(org.id), kind="organization", display_name="Client Connu")
    lead = Lead.objects.create(organization=org, display_name="CLIENT CONNU", email="c@known.test")

    opportunity = convert_lead_to_opportunity(lead_id=str(lead.id), label="Projet X")
    assert opportunity.party_id == existing.id  # no duplicated party
    again = convert_lead_to_opportunity(lead_id=str(lead.id), label="Projet X bis")
    assert again.id == opportunity.id  # idempotent

    lead.refresh_from_db()
    assert lead.status == "converted"


@pytest.mark.django_db
def test_opportunity_loss_requires_reason() -> None:
    org = _make_org("crm-loss")
    lead = Lead.objects.create(organization=org, display_name="Prospect P")
    opportunity = convert_lead_to_opportunity(lead_id=str(lead.id), label="Deal")

    with pytest.raises(ValueError, match="loss reason"):
        lose_opportunity(opportunity_id=str(opportunity.id), reason="   ")

    lost = lose_opportunity(opportunity_id=str(opportunity.id), reason="Budget insuffisant")
    assert lost.status == "lost"
    with pytest.raises(ValueError, match="open opportunity"):
        win_opportunity(opportunity_id=str(opportunity.id))


@pytest.mark.django_db
def test_price_resolution_at_historical_date() -> None:
    org = _make_org("catalog-price")
    item = CatalogItem.objects.create(organization=org, code="consulting", label="Conseil")
    set_price(item_id=str(item.id), amount=Decimal("100.0000"), valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31))
    set_price(item_id=str(item.id), amount=Decimal("120.0000"), valid_from=date(2026, 1, 1))

    assert resolve_price(item_id=str(item.id), on_date=date(2025, 6, 1)).amount == Decimal("100.0000")
    assert resolve_price(item_id=str(item.id), on_date=date(2026, 7, 1)).amount == Decimal("120.0000")

    item.is_active = False
    item.save(update_fields=["is_active"])
    with pytest.raises(ValueError, match="archived"):
        resolve_price(item_id=str(item.id), on_date=date(2026, 7, 1))


def _quote_with_lines(org, party):
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation A",
        quantity=Decimal("3"),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("20"),
    )
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation B",
        quantity=Decimal("1.5"),
        unit_price=Decimal("80.00"),
        tax_rate=Decimal("10"),
    )
    return quote


@pytest.mark.django_db
def test_quote_totals_frozen_on_send_and_revision_flow() -> None:
    org = _make_org("quote-flow")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client Q")
    quote = _quote_with_lines(org, party)

    sent = send_quote(quote_id=str(quote.id))
    # 3*100 = 300.00 (+20% = 60.00) ; 1.5*80 = 120.00 (+10% = 12.00)
    assert sent.total_excl_tax == Decimal("420.00")
    assert sent.total_tax == Decimal("72.00")
    assert sent.total_incl_tax == Decimal("492.00")

    with pytest.raises(ValueError, match="draft quote"):
        add_quote_line(
            quote_id=str(quote.id),
            description="Ajout interdit",
            quantity=Decimal("1"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("20"),
        )

    revision = revise_quote(quote_id=str(quote.id))
    assert revision.version == 2
    assert revision.previous_version_id == quote.id
    assert revision.lines.count() == 2
    assert revision.status == "draft"


@pytest.mark.django_db
def test_quote_acceptance_requires_proof_and_conversion_is_idempotent() -> None:
    org = _make_org("quote-accept")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client A")
    quote = _quote_with_lines(org, party)
    send_quote(quote_id=str(quote.id))

    with pytest.raises(ValueError, match="proof is required"):
        accept_quote(quote_id=str(quote.id), acceptance_proof="  ")

    accepted = accept_quote(quote_id=str(quote.id), acceptance_proof="signature portail 2026-07-18")
    assert accepted.accepted_at is not None

    order_1 = convert_quote_to_order(quote_id=str(quote.id))
    order_2 = convert_quote_to_order(quote_id=str(quote.id))
    assert order_1.id == order_2.id  # idempotent conversion
    assert order_1.total_incl_tax == accepted.total_incl_tax  # same amounts everywhere
    assert order_1.lines.count() == 2


@pytest.mark.django_db
def test_delivery_capped_at_ordered_quantity() -> None:
    org = _make_org("delivery-cap")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client L")
    quote = _quote_with_lines(org, party)
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="ok")
    order = convert_quote_to_order(quote_id=str(quote.id))
    line_a = order.lines.get(position=1)  # qty 3
    line_b = order.lines.get(position=2)  # qty 1.5

    record_delivery(order_id=str(order.id), items=[(str(line_a.id), Decimal("2"))])
    line_a.refresh_from_db()
    assert line_a.delivered_quantity == Decimal("2")

    with pytest.raises(ValueError, match="exceeds remaining"):
        record_delivery(order_id=str(order.id), items=[(str(line_a.id), Decimal("2"))])

    record_delivery(
        order_id=str(order.id),
        items=[(str(line_a.id), Decimal("1")), (str(line_b.id), Decimal("1.5"))],
    )
    order.refresh_from_db()
    assert order.status == "fulfilled"
