from django.db import transaction

from .models import SavedView, UserTablePreference


@transaction.atomic
def save_view(*, organization_id: str, user_id: int, view_key: str, name: str, parameters: dict) -> SavedView:
    view, _ = SavedView.objects.update_or_create(
        user_id=user_id,
        view_key=view_key,
        name=name,
        defaults={"organization_id": organization_id, "parameters": parameters},
    )
    return view


@transaction.atomic
def save_table_preference(*, user_id: int, table_key: str, preferences: dict) -> UserTablePreference:
    preference, _ = UserTablePreference.objects.update_or_create(
        user_id=user_id,
        table_key=table_key,
        defaults={"preferences": preferences},
    )
    return preference
