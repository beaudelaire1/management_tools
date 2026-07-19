import hashlib
import json
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from modular_brix.foundation.audit.services import record_audit_event

from .models import BankStatement, BankTransaction, FinancialAccount, TransactionMatch


def _statement_hash(statement_date: date, opening: Decimal, closing: Decimal, lines: list[dict]) -> str:
    payload = json.dumps(
        {"date": statement_date.isoformat(), "opening": str(opening), "closing": str(closing), "lines": lines},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@transaction.atomic
def import_statement(
    *,
    account_id: str,
    statement_date: date,
    opening_balance: Decimal,
    closing_balance: Decimal,
    lines: list[dict],
) -> BankStatement:
    """Idempotent import: the same content re-imported returns the stored statement.

    The statement is refused when its own balances do not add up, so a broken
    export never enters reconciliation.
    """
    account = FinancialAccount.objects.select_for_update().get(id=account_id)
    normalized = [
        {"value_date": str(line["value_date"]), "amount": str(line["amount"]), "label": line["label"]}
        for line in lines
    ]
    import_hash = _statement_hash(statement_date, opening_balance, closing_balance, normalized)
    existing = BankStatement.objects.filter(account=account, import_hash=import_hash).first()
    if existing is not None:
        return existing
    movement_total = sum(Decimal(line["amount"]) for line in normalized) or Decimal("0.00")
    if opening_balance + movement_total != closing_balance:
        raise ValueError("Statement balances are inconsistent with its transactions.")
    statement = BankStatement.objects.create(
        account=account,
        statement_date=statement_date,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        import_hash=import_hash,
    )
    for position, line in enumerate(lines, start=1):
        BankTransaction.objects.create(
            statement=statement,
            position=position,
            value_date=line["value_date"],
            amount=Decimal(str(line["amount"])),
            label=line["label"],
        )
    return statement


def matched_amount(bank_transaction: BankTransaction) -> Decimal:
    total = bank_transaction.matches.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


@transaction.atomic
def match_transaction(*, transaction_id: str, payment_id: str, amount: Decimal) -> TransactionMatch:
    """One-to-many matching, capped by the absolute transaction amount."""
    bank_transaction = BankTransaction.objects.select_for_update().get(id=transaction_id)
    if amount <= 0:
        raise ValueError("A match amount must be positive.")
    capacity = abs(bank_transaction.amount) - matched_amount(bank_transaction)
    if amount > capacity:
        raise ValueError(f"Match amount {amount} exceeds the unmatched remainder {capacity}.")
    return TransactionMatch.objects.create(
        transaction=bank_transaction, payment_id=payment_id, amount=amount
    )


@transaction.atomic
def unmatch(*, match_id: str, actor_user_id: int | None, reason: str) -> None:
    """Unreconciling is allowed but always audited (spec C06)."""
    if not reason.strip():
        raise ValueError("Unmatching requires a reason.")
    match = TransactionMatch.objects.select_related("transaction__statement__account").get(id=match_id)
    record_audit_event(
        organization_id=str(match.transaction.statement.account.organization_id),
        actor_user_id=actor_user_id,
        event_type="banking.transaction.unmatched",
        object_type="banking.TransactionMatch",
        object_id=str(match.id),
        outcome="success",
        context={"reason": reason.strip(), "amount": str(match.amount)},
    )
    match.delete()


def unreconciled_transactions(*, statement_id: str) -> list[BankTransaction]:
    return [
        bank_transaction
        for bank_transaction in BankTransaction.objects.filter(statement_id=statement_id)
        if matched_amount(bank_transaction) != abs(bank_transaction.amount)
    ]
