from django.apps import AppConfig


class TaxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.tax"
    label = "finance_tax"
