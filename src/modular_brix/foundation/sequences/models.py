import uuid

from django.db import models


class SequenceCounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sequence_counters",
    )
    code = models.SlugField(max_length=80)
    period = models.CharField(max_length=16)
    last_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "period"],
                name="uq_sequence_org_code_period",
            )
        ]
