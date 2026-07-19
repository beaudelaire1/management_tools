from django.db import transaction

from modular_brix.management.parties.services import add_party_role, create_party, find_duplicate_parties

from .models import Lead, Opportunity


@transaction.atomic
def convert_lead_to_opportunity(*, lead_id: str, label: str, probability: int = 10) -> Opportunity:
    """Convert without duplicating the party; the lead history is preserved (spec G02)."""
    lead = Lead.objects.select_for_update().get(id=lead_id)
    if lead.status == "converted" and hasattr(lead, "opportunity"):
        return lead.opportunity  # Idempotent conversion.

    existing = find_duplicate_parties(
        organization_id=str(lead.organization_id),
        display_name=lead.display_name,
    ).first()
    party = existing or create_party(
        organization_id=str(lead.organization_id),
        kind="organization",
        display_name=lead.display_name,
        email=lead.email,
    )
    add_party_role(party_id=str(party.id), role_type="customer")

    opportunity = Opportunity.objects.create(
        organization_id=lead.organization_id,
        party=party,
        lead=lead,
        label=label,
        probability=probability,
    )
    lead.party = party
    lead.status = "converted"
    lead.save(update_fields=["party", "status"])
    return opportunity


@transaction.atomic
def lose_opportunity(*, opportunity_id: str, reason: str) -> Opportunity:
    if not reason.strip():
        raise ValueError("A loss reason is required.")
    opportunity = Opportunity.objects.select_for_update().get(id=opportunity_id)
    if opportunity.status != "open":
        raise ValueError("Only an open opportunity can be lost.")
    opportunity.status = "lost"
    opportunity.loss_reason = reason.strip()
    opportunity.save(update_fields=["status", "loss_reason"])
    return opportunity


@transaction.atomic
def win_opportunity(*, opportunity_id: str) -> Opportunity:
    opportunity = Opportunity.objects.select_for_update().get(id=opportunity_id)
    if opportunity.status != "open":
        raise ValueError("Only an open opportunity can be won.")
    opportunity.status = "won"
    opportunity.probability = 100
    opportunity.save(update_fields=["status", "probability"])
    return opportunity
