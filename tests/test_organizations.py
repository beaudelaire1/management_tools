import pytest

from modular_brix.foundation.organizations.models import Organization
from modular_brix.foundation.organizations.policies import can_view_organization
from modular_brix.foundation.organizations.selectors import list_establishments_for_organization
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment


@pytest.mark.django_db
def test_health_endpoint(client) -> None:
    response = client.get("/org/health/")
    assert response.status_code == 200
    assert response.content == b"organizations-ok"


@pytest.mark.django_db
def test_create_organization_creates_default_establishment() -> None:
    org = create_organization_with_default_establishment(
        slug="alpha",
        legal_name="Alpha Corp",
        legal_identifier="SIREN123",
        country_code="fr",
    )

    assert Organization.objects.count() == 1
    assert org.establishments.count() == 1
    assert list_establishments_for_organization(str(org.id)).count() == 1


@pytest.mark.django_db
def test_organization_isolation_policy() -> None:
    alpha = create_organization_with_default_establishment(
        slug="alpha",
        legal_name="Alpha Corp",
        legal_identifier="SIREN123",
        country_code="FR",
    )
    beta = create_organization_with_default_establishment(
        slug="beta",
        legal_name="Beta Corp",
        legal_identifier="SIREN456",
        country_code="FR",
    )

    assert can_view_organization(str(alpha.id), alpha) is True
    assert can_view_organization(str(alpha.id), beta) is False
