import uuid

from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    legal_name = models.CharField(max_length=255)
    legal_identifier = models.CharField(max_length=64)
    country_code = models.CharField(max_length=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["legal_identifier", "country_code"],
                name="uq_org_legal_identifier_country",
            )
        ]

    def __str__(self) -> str:
        return self.legal_name


class Establishment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="establishments")
    code = models.CharField(max_length=32)
    display_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uq_establishment_org_code",
            )
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.code})"
