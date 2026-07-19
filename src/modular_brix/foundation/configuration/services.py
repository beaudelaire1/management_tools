from django.db import transaction

from .models import Feature, FeatureAssignment, SettingDefinition, SettingValue, VocabularyTerm


def is_feature_enabled(*, organization_id: str, feature_code: str) -> bool:
    return FeatureAssignment.objects.filter(
        organization_id=organization_id,
        feature__code=feature_code,
        is_enabled=True,
    ).exists()


@transaction.atomic
def enable_feature(*, organization_id: str, feature_code: str) -> FeatureAssignment:
    feature = Feature.objects.get(code=feature_code)
    for dependency_code in feature.depends_on:
        if not is_feature_enabled(organization_id=organization_id, feature_code=dependency_code):
            raise ValueError(f"Feature '{feature_code}' requires '{dependency_code}' to be enabled first.")
    assignment, _ = FeatureAssignment.objects.update_or_create(
        organization_id=organization_id,
        feature=feature,
        defaults={"is_enabled": True},
    )
    return assignment


@transaction.atomic
def disable_feature(*, organization_id: str, feature_code: str) -> None:
    FeatureAssignment.objects.filter(
        organization_id=organization_id,
        feature__code=feature_code,
    ).update(is_enabled=False)


@transaction.atomic
def set_setting(*, organization_id: str, code: str, value) -> SettingValue:
    definition = SettingDefinition.objects.get(code=code)
    definition.validate_value(value)
    setting, _ = SettingValue.objects.update_or_create(
        organization_id=organization_id,
        definition=definition,
        defaults={"value": value},
    )
    return setting


def get_setting(*, organization_id: str, code: str):
    definition = SettingDefinition.objects.get(code=code)
    stored = SettingValue.objects.filter(organization_id=organization_id, definition=definition).first()
    return stored.value if stored is not None else definition.default_value


@transaction.atomic
def set_vocabulary_term(*, organization_id: str, key: str, label: str) -> VocabularyTerm:
    term, _ = VocabularyTerm.objects.update_or_create(
        organization_id=organization_id,
        key=key,
        defaults={"label": label},
    )
    return term


def get_vocabulary_label(*, organization_id: str, key: str, default: str) -> str:
    term = VocabularyTerm.objects.filter(organization_id=organization_id, key=key).first()
    return term.label if term is not None else default


@transaction.atomic
def set_custom_field(*, definition_id: str, object_id: str, value):
    """Typed validation happens at write time; a bad value never lands (F08)."""
    from datetime import date

    from .models import CustomFieldDefinition, CustomFieldValue

    definition = CustomFieldDefinition.objects.get(id=definition_id)
    if value is None:
        if definition.is_required:
            raise ValueError(f"Custom field {definition.key} is required.")
    elif definition.kind == "text":
        if not isinstance(value, str):
            raise ValueError(f"Custom field {definition.key} expects text.")
    elif definition.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Custom field {definition.key} expects a number.")
    elif definition.kind == "date":
        try:
            date.fromisoformat(str(value))
        except ValueError:
            raise ValueError(f"Custom field {definition.key} expects an ISO date.") from None
    elif definition.kind == "choice":
        if value not in definition.choices:
            raise ValueError(f"Custom field {definition.key} expects one of {definition.choices}.")
    stored, _ = CustomFieldValue.objects.update_or_create(
        definition=definition, object_id=str(object_id), defaults={"value": value}
    )
    return stored


def missing_required_custom_fields(*, organization_id: str, model_label: str, object_id: str) -> list[str]:
    from .models import CustomFieldDefinition

    missing = []
    definitions = CustomFieldDefinition.objects.filter(
        organization_id=organization_id, model_label=model_label, is_required=True
    )
    for definition in definitions:
        stored = definition.values.filter(object_id=str(object_id)).first()
        if stored is None or stored.value in (None, ""):
            missing.append(definition.key)
    return missing
