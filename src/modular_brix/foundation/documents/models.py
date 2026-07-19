import uuid

from django.conf import settings
from django.db import models


class DocumentCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="documents",
    )
    category = models.ForeignKey(DocumentCategory, on_delete=models.PROTECT, related_name="documents")
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64)
    is_regulatory = models.BooleanField(default=False)
    access_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "object_type", "object_id"], name="idx_doc_object_scope"),
        ]


SIGNATURE_IMMUTABLE_ERROR = "A document signature can never be modified or deleted."


class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    file_name = models.CharField(max_length=255)
    content_sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_versions",
    )
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="uq_document_version_number",
            )
        ]
        indexes = [
            models.Index(fields=["document", "is_current"], name="idx_document_current"),
        ]


class DocumentSignature(models.Model):
    """Signature over one exact version content: what was signed can never drift (F06)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(DocumentVersion, on_delete=models.PROTECT, related_name="signatures")
    signer_name = models.CharField(max_length=255)
    signed_content_sha256 = models.CharField(max_length=64)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "signer_name"], name="uq_document_signature_signer"
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(SIGNATURE_IMMUTABLE_ERROR)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(SIGNATURE_IMMUTABLE_ERROR)
