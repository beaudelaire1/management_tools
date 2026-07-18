from .models import Organization


def can_view_organization(actor_organization_id: str, organization: Organization) -> bool:
    return str(organization.id) == str(actor_organization_id)
