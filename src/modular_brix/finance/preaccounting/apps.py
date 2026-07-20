from django.apps import AppConfig


class PreaccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.preaccounting"
    label = "finance_preaccounting"
