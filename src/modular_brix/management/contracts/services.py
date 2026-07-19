from datetime import date, timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Contract, ContractVersion, Subscription, SubscriptionInvoiceRun


@transaction.atomic
def add_version(*, contract_id: str, terms: str) -> ContractVersion:
    contract = Contract.objects.select_for_update().get(id=contract_id)
    if contract.status == "terminated":
        raise ValueError("A terminated contract cannot receive new versions.")
    last = contract.versions.aggregate(top=Max("version_number"))["top"] or 0
    return ContractVersion.objects.create(contract=contract, version_number=last + 1, terms=terms)


@transaction.atomic
def sign_version(*, version_id: str) -> ContractVersion:
    version = ContractVersion.objects.select_for_update().get(id=version_id)
    if version.signed_at is not None:
        raise ValueError("This contract version is already signed.")
    version.signed_at = timezone.now()
    version.save()
    contract = version.contract
    if contract.status == "draft":
        contract.status = "active"
        contract.save(update_fields=["status"])
    return version


@transaction.atomic
def renew_contract(*, contract_id: str, new_end_date: date) -> Contract:
    """Renewal is always an explicit, dated act; no silent extension (spec G12)."""
    contract = Contract.objects.select_for_update().get(id=contract_id)
    if contract.status != "active":
        raise ValueError("Only an active contract can be renewed.")
    if contract.ends_on is not None and new_end_date <= contract.ends_on:
        raise ValueError("A renewal must extend the contract end date.")
    contract.ends_on = new_end_date
    contract.save(update_fields=["ends_on"])
    return contract


@transaction.atomic
def terminate_contract(*, contract_id: str) -> Contract:
    """Termination keeps the whole history readable; nothing is deleted."""
    contract = Contract.objects.select_for_update().get(id=contract_id)
    if contract.status == "terminated":
        raise ValueError("This contract is already terminated.")
    contract.status = "terminated"
    contract.terminated_at = timezone.now()
    contract.save(update_fields=["status", "terminated_at"])
    return contract


def expiring_contracts(*, organization_id: str, horizon_days: int = 60) -> list[Contract]:
    """Contracts whose notice window opens within the horizon: no silent deadline."""
    today = timezone.now().date()
    contracts = Contract.objects.filter(
        organization_id=organization_id, status="active", ends_on__isnull=False
    )
    return [
        contract
        for contract in contracts
        if contract.ends_on - timedelta(days=contract.notice_days) <= today + timedelta(days=horizon_days)
    ]


@transaction.atomic
def bill_subscription_period(*, contract_id: str, period: str):
    """Idempotent recurring billing: one invoice per contract and period, replay returns it."""
    contract = Contract.objects.select_for_update().get(id=contract_id)
    if contract.status != "active":
        raise ValueError("Only an active contract can be billed.")
    existing = SubscriptionInvoiceRun.objects.filter(contract=contract, period=period).first()
    if existing is not None:
        return existing.invoice
    subscriptions = list(Subscription.objects.filter(contract=contract, is_active=True))
    if not subscriptions:
        raise ValueError("This contract has no active subscription to bill.")
    from modular_brix.finance.billing.models import Invoice, InvoiceLine

    invoice = Invoice.objects.create(
        organization_id=contract.organization_id, party_id=contract.party_id
    )
    for position, subscription in enumerate(subscriptions, start=1):
        InvoiceLine.objects.create(
            invoice=invoice,
            position=position,
            description=f"{subscription.item.label} — abonnement {period}",
            quantity=subscription.quantity,
            unit_price=subscription.unit_price,
            tax_rate=subscription.tax_rate,
        )
    SubscriptionInvoiceRun.objects.create(contract=contract, period=period, invoice=invoice)
    return invoice
