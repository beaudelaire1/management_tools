from django.db import transaction
from django.db.models import Max

from .models import Document, DocumentCategory, DocumentVersion


@transaction.atomic
def create_document(
    *,
    organization_id: str,
    category_code: str,
    category_label: str,
    object_type: str,
    object_id: str,
    is_regulatory: bool,
) -> Document:
    category, _ = DocumentCategory.objects.get_or_create(
        code=category_code,
        defaults={"label": category_label},
    )
    return Document.objects.create(
        organization_id=organization_id,
        category=category,
        object_type=object_type,
        object_id=object_id,
        is_regulatory=is_regulatory,
    )


@transaction.atomic
def add_document_version(
    *,
    document_id: str,
    file_name: str,
    content_sha256: str,
    byte_size: int,
    created_by_user_id: int | None,
    allow_regulatory_replacement: bool = False,
) -> DocumentVersion:
    document = Document.objects.select_for_update().get(id=document_id)
    latest_number = document.versions.aggregate(max_number=Max("version_number"))["max_number"] or 0
    next_number = latest_number + 1

    if document.is_regulatory and latest_number > 0 and not allow_regulatory_replacement:
        raise ValueError("Regulatory document versions cannot be replaced silently.")

    DocumentVersion.objects.filter(document=document, is_current=True).update(is_current=False)

    return DocumentVersion.objects.create(
        document=document,
        version_number=next_number,
        file_name=file_name,
        content_sha256=content_sha256,
        byte_size=byte_size,
        created_by_user_id=created_by_user_id,
        is_current=True,
    )


@transaction.atomic
def revoke_document_access(*, document_id: str) -> None:
    Document.objects.filter(id=document_id).update(access_revoked=True)
