import unicodedata

from django.db import transaction
from django.db.models import QuerySet

from .models import Party, PartyRole


def normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())


@transaction.atomic
def create_party(*, organization_id: str, kind: str, display_name: str, email: str = "") -> Party:
    return Party.objects.create(
        organization_id=organization_id,
        kind=kind,
        display_name=display_name,
        normalized_name=normalize_name(display_name),
        email=email.strip().lower(),
    )


def find_duplicate_parties(*, organization_id: str, display_name: str) -> QuerySet[Party]:
    """Accent-insensitive, case-insensitive duplicate lookup."""
    return Party.objects.filter(
        organization_id=organization_id,
        normalized_name=normalize_name(display_name),
        is_active=True,
        merged_into__isnull=True,
    )


@transaction.atomic
def add_party_role(*, party_id: str, role_type: str) -> PartyRole:
    """A party can hold several roles (customer AND supplier) without duplication."""
    role, _ = PartyRole.objects.get_or_create(party_id=party_id, role_type=role_type)
    if not role.is_active:
        role.is_active = True
        role.save(update_fields=["is_active"])
    return role


@transaction.atomic
def merge_parties(*, primary_id: str, duplicate_id: str) -> Party:
    """Controlled merge: the duplicate is deactivated, never deleted; history stays readable."""
    if str(primary_id) == str(duplicate_id):
        raise ValueError("A party cannot be merged into itself.")
    duplicate = Party.objects.select_for_update().get(id=duplicate_id)
    primary = Party.objects.select_for_update().get(id=primary_id)
    if duplicate.organization_id != primary.organization_id:
        raise ValueError("Parties from different organizations cannot be merged.")
    if duplicate.merged_into_id is not None:
        raise ValueError("This party has already been merged.")

    for role in duplicate.roles.filter(is_active=True):
        add_party_role(party_id=str(primary.id), role_type=role.role_type)

    duplicate.merged_into = primary
    duplicate.is_active = False
    duplicate.save(update_fields=["merged_into", "is_active"])
    return primary
