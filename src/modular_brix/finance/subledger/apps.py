from django.apps import AppConfig


class SubledgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.subledger"
    label = "finance_subledger"
