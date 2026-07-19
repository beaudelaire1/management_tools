from django.db import transaction

from .models import Establishment, Organization


@transaction.atomic
def create_organization_with_default_establishment(
    slug: str,
    legal_name: str,
    legal_identifier: str,
    country_code: str,
) -> Organization:
    organization = Organization.objects.create(
        slug=slug,
        legal_name=legal_name,
        legal_identifier=legal_identifier,
        country_code=country_code.upper(),
    )
    Establishment.objects.create(
        organization=organization,
        code="MAIN",
        display_name="Main establishment",
    )
    return organization


@transaction.atomic
def archive_organization(*, organization_id: str) -> Organization:
    """Archive without deleting: historical references stay intact (spec F01)."""
    organization = Organization.objects.select_for_update().get(id=organization_id)
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    organization.establishments.update(is_active=False)
    return organization
