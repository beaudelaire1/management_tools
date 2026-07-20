import uuid
from decimal import Decimal, InvalidOperation

from django.db import models


class Feature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    depends_on = models.JSONField(default=list)


class FeatureAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feature_assignments",
    )
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT, related_name="assignments")
    is_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "feature"], name="uq_feature_assignment")
        ]


class SettingDefinition(models.Model):
    VALUE_TYPES = ("string", "integer", "boolean", "decimal")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    value_type = models.CharField(max_length=16)
    default_value = models.JSONField(null=True, blank=True)

    def validate_value(self, value) -> None:
        if self.value_type == "string" and not isinstance(value, str):
            raise ValueError(f"Setting {self.code} expects a string.")
        if self.value_type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"Setting {self.code} expects an integer.")
        if self.value_type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Setting {self.code} expects a boolean.")
        if self.value_type == "decimal":
            try:
                Decimal(str(value))
            except (InvalidOperation, TypeError):
                raise ValueError(f"Setting {self.code} expects a decimal.") from None


class SettingValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="setting_values",
    )
    definition = models.ForeignKey(SettingDefinition, on_delete=models.PROTECT, related_name="values")
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "definition"], name="uq_setting_value")
        ]


class VocabularyTerm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="vocabulary_terms",
    )
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="uq_vocabulary_org_key")
        ]


class CustomFieldDefinition(models.Model):
    """Client-defined field on a model, typed and optionally required (F08)."""

    KINDS = ("text", "number", "date", "choice")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "foundation_organizations.Organization",
        on_delete=models.PROTECT,
        related_name="custom_field_definitions",
    )
    model_label = models.CharField(max_length=64)  # e.g. management_parties.Party
    key = models.SlugField(max_length=64)
    kind = models.CharField(max_length=16)
    is_required = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "model_label", "key"], name="uq_custom_field_key"
            )
        ]


class CustomFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(CustomFieldDefinition, on_delete=models.CASCADE, related_name="values")
    object_id = models.CharField(max_length=64)
    value = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["definition", "object_id"], name="uq_custom_field_value")
        ]
