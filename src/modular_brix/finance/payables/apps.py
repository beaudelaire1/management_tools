from django.apps import AppConfig


class PayablesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.payables"
    label = "finance_payables"
