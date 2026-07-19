import uuid

from django.db import models


class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="leads",
    )
    display_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=16, default="new")  # new | converted | discarded
    party = models.ForeignKey(
        "management_parties.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="leads",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Opportunity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    party = models.ForeignKey(
        "management_parties.Party",
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    lead = models.OneToOneField(Lead, null=True, blank=True, on_delete=models.PROTECT, related_name="opportunity")
    label = models.CharField(max_length=255)
    stage = models.CharField(max_length=32, default="qualification")
    probability = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, default="open")  # open | won | lost
    loss_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
