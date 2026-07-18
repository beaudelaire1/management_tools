from .models import Document


def can_access_document(*, actor_organization_id: str, document: Document) -> bool:
    return (str(document.organization_id) == str(actor_organization_id)) and (not document.access_revoked)
