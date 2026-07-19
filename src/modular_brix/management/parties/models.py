import uuid

from django.db import models


class Party(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="parties",
    )
    kind = models.CharField(max_length=16)  # person | organization
    display_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(blank=True)
    merged_into = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="merged_duplicates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "normalized_name"], name="idx_party_org_norm_name"),
        ]


class PartyRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="roles")
    role_type = models.CharField(max_length=24)  # customer | supplier | partner | contact
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["party", "role_type"], name="uq_party_role_type")
        ]


class PartyIdentifier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="identifiers")
    scheme = models.CharField(max_length=24)  # siren | vat | duns | other
    value = models.CharField(max_length=64)
    valid_from = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["party", "scheme", "value"], name="uq_party_identifier")
        ]
