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
