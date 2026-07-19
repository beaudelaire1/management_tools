from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.finance.ledger"
    label = "finance_ledger"
