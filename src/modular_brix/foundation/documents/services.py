from collections.abc import Callable

from django.db import transaction
from django.db.models import Max

from .models import Document, DocumentCategory, DocumentSignature, DocumentVersion

# File-acceptance controls (F06): a blocked-extension list plus pluggable scanners
# (an antivirus integration registers a callable returning True when the file is clean).
BLOCKED_EXTENSIONS = frozenset({"exe", "bat", "cmd", "com", "scr", "msi", "vbs", "ps1"})

FileScanner = Callable[[str, str], bool]  # (file_name, content_sha256) -> clean?

_SCANNERS: list[FileScanner] = []


def register_file_scanner(scanner: FileScanner) -> None:
    _SCANNERS.append(scanner)


def clear_file_scanners() -> None:
    _SCANNERS.clear()


def ensure_file_accepted(*, file_name: str, content_sha256: str) -> None:
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension in BLOCKED_EXTENSIONS:
        raise ValueError(f"Files with the {extension} extension are not accepted.")
    for scanner in _SCANNERS:
        if not scanner(file_name, content_sha256):
            raise ValueError(f"File {file_name} was rejected by a content scanner.")


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
    ensure_file_accepted(file_name=file_name, content_sha256=content_sha256)
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


@transaction.atomic
def sign_document_version(*, version_id: str, signer_name: str) -> DocumentSignature:
    """The signature binds the signer to the exact stored content hash (F06)."""
    version = DocumentVersion.objects.get(id=version_id)
    if not signer_name.strip():
        raise ValueError("A signature requires a signer name.")
    return DocumentSignature.objects.create(
        version=version,
        signer_name=signer_name.strip(),
        signed_content_sha256=version.content_sha256,
    )
