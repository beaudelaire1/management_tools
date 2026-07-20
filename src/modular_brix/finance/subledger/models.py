import uuid

from django.db import models


class OpenItem(models.Model):
    """A customer or supplier open position awaiting settlement (spec C09)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="open_items"
    )
    party = models.ForeignKey("management_parties.Party", on_delete=models.PROTECT, related_name="open_items")
    direction = models.CharField(max_length=8)  # debit | credit
    source_kind = models.CharField(max_length=32)  # invoice | payment | credit_note | ...
    source_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_open_item_positive"),
            models.UniqueConstraint(
                fields=["organization", "source_kind", "source_id"], name="uq_open_item_source"
            ),
        ]


class LetteringGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization", on_delete=models.PROTECT, related_name="lettering_groups"
    )
    party = models.ForeignKey(
        "management_parties.Party", on_delete=models.PROTECT, related_name="lettering_groups"
    )
    code = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_lettering_code")
        ]


class Settlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(LetteringGroup, on_delete=models.CASCADE, related_name="settlements")
    open_item = models.ForeignKey(OpenItem, on_delete=models.PROTECT, related_name="settlements")
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_settlement_positive")
        ]
