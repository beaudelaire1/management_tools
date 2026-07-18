from django.db.models import QuerySet

from .models import DocumentVersion


def list_document_versions(*, document_id: str) -> QuerySet[DocumentVersion]:
    return DocumentVersion.objects.filter(document_id=document_id).order_by("version_number")
