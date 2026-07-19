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


class LegalEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="legal_entities")
    name = models.CharField(max_length=255)
    legal_form = models.CharField(max_length=80, blank=True)
    registration_number = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=120)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uq_department_org_name")
        ]


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="teams")
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "name"], name="uq_team_department_name")
        ]


class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="addresses")
    address_type = models.CharField(max_length=32)
    line_1 = models.CharField(max_length=255)
    line_2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=16)
    city = models.CharField(max_length=120)
    country_code = models.CharField(max_length=2)
    is_active = models.BooleanField(default=True)


class LegalProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(Organization, on_delete=models.PROTECT, related_name="legal_profile")
    share_capital = models.CharField(max_length=64, blank=True)
    registry_city = models.CharField(max_length=120, blank=True)


class FiscalProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(Organization, on_delete=models.PROTECT, related_name="fiscal_profile")
    vat_number = models.CharField(max_length=32, blank=True)
    fiscal_regime = models.CharField(max_length=64, blank=True)


class BrandSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(Organization, on_delete=models.PROTECT, related_name="brand_settings")
    display_name = models.CharField(max_length=255)
    primary_color = models.CharField(max_length=7, default="#1a1a2e")
    secondary_color = models.CharField(max_length=7, default="#c9a961")
    logo_path = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
