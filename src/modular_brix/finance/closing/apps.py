from django.apps import AppConfig


class ClosingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.closing"
    label = "finance_closing"
