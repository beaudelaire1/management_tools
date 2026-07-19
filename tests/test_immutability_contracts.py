import importlib
import inspect

from modular_brix.finance.billing.models import (
    INVOICE_CREATE_DRAFT_ERROR,
    INVOICE_IMMUTABLE_ERROR,
    INVOICE_LINE_IMMUTABLE_ERROR,
)
from modular_brix.management.sales.models import (
    QUOTE_ACCEPTANCE_ERROR,
    QUOTE_CREATE_DRAFT_ERROR,
    QUOTE_IMMUTABLE_ERROR,
    QUOTE_LINE_IMMUTABLE_ERROR,
    QUOTE_STATUS_TRANSITION_ERROR,
)


def test_postgresql_invoice_trigger_messages_match_orm_contract() -> None:
    migration = importlib.import_module(
        "modular_brix.finance.billing.migrations.0004_financial_immutability_triggers"
    )
    trigger_source = inspect.getsource(migration.create_financial_immutability_triggers)

    assert INVOICE_CREATE_DRAFT_ERROR in trigger_source
    assert INVOICE_IMMUTABLE_ERROR in trigger_source
    assert INVOICE_LINE_IMMUTABLE_ERROR in trigger_source


def test_postgresql_quote_trigger_messages_match_orm_contract() -> None:
    migration = importlib.import_module(
        "modular_brix.management.sales.migrations.0002_quote_immutability_triggers"
    )
    trigger_source = inspect.getsource(migration.create_quote_immutability_triggers)

    assert QUOTE_CREATE_DRAFT_ERROR in trigger_source
    assert QUOTE_IMMUTABLE_ERROR in trigger_source
    assert QUOTE_LINE_IMMUTABLE_ERROR in trigger_source
    assert QUOTE_STATUS_TRANSITION_ERROR in trigger_source
    assert QUOTE_ACCEPTANCE_ERROR in trigger_source
