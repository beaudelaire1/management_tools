from django.apps import AppConfig


class FixedAssetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.fixed_assets"
    label = "finance_fixed_assets"
