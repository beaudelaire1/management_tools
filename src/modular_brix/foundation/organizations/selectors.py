from django.db.models import QuerySet

from .models import Establishment


def list_establishments_for_organization(organization_id: str) -> QuerySet[Establishment]:
    return Establishment.objects.filter(organization_id=organization_id, is_active=True)
