"""C14: electronic invoicing through pluggable platform adapters.

An adapter is a callable taking the structured payload and returning
``(status, message)``. Registering a different adapter changes the platform
without touching the billing brick. The ordinary PDF sent by email is NOT the
regulated electronic invoice; production use requires a registered platform
(plateforme agréée) behind a real adapter.
"""

import hashlib
import json
from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.billing.services import missing_mandatory_mentions

from .models import ElectronicInvoice, ProviderConfiguration, Transmission

Adapter = Callable[[dict], tuple[str, str]]

_ADAPTERS: dict[str, Adapter] = {}


def register_adapter(code: str, adapter: Adapter) -> None:
    _ADAPTERS[code] = adapter


def _reference_adapter(payload: dict) -> tuple[str, str]:
    """In-memory reference adapter used by tests and local runs; always accepts."""
    return "accepted", f"accepted {payload['number']}"


register_adapter("reference", _reference_adapter)


def build_payload(invoice: Invoice) -> dict:
    """Structured data built from the frozen C01 snapshot: totals, parties, lines, mentions."""
    return {
        "number": invoice.number,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "currency": invoice.currency,
        "seller": {
            "name": invoice.seller_name,
            "legal_identifier": invoice.seller_legal_identifier,
            "vat_number": invoice.seller_vat_number,
            "address": invoice.seller_address,
        },
        "buyer": {
            "name": invoice.buyer_name,
            "vat_number": invoice.buyer_vat_number,
            "address": invoice.buyer_address,
        },
        "totals": {
            "excl_tax": str(invoice.total_excl_tax),
            "tax": str(invoice.total_tax),
            "incl_tax": str(invoice.total_incl_tax),
        },
        "lines": [
            {
                "position": line.position,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "tax_rate": str(line.tax_rate),
            }
            for line in invoice.lines.order_by("position")
        ],
    }


@transaction.atomic
def prepare_electronic_invoice(*, invoice_id: str) -> ElectronicInvoice:
    """Pre-validation then payload freeze; incomplete mention sets never leave the system."""
    invoice = Invoice.objects.get(id=invoice_id)
    if invoice.status != "issued":
        raise ValueError("Only an issued invoice can be transmitted electronically.")
    missing = missing_mandatory_mentions(invoice)
    if missing:
        raise ValueError("Electronic transmission blocked; missing mandatory mentions: " + ", ".join(missing))
    existing = ElectronicInvoice.objects.filter(invoice=invoice).first()
    if existing is not None:
        return existing
    payload = build_payload(invoice)
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return ElectronicInvoice.objects.create(invoice=invoice, payload=payload, payload_hash=payload_hash)


@transaction.atomic
def transmit(*, electronic_invoice_id: str, idempotency_key: str) -> Transmission:
    """Idempotent transmission: replaying a key returns the stored transmission,
    so an invoice is never emitted twice to the platform (spec C14)."""
    electronic_invoice = (
        ElectronicInvoice.objects.select_for_update()
        .select_related("invoice__organization")
        .get(id=electronic_invoice_id)
    )
    existing = Transmission.objects.filter(
        electronic_invoice=electronic_invoice, idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        return existing
    configuration = ProviderConfiguration.objects.filter(
        organization_id=electronic_invoice.invoice.organization_id
    ).first()
    if configuration is None:
        raise ValueError("No e-invoicing provider is configured for this organization.")
    adapter = _ADAPTERS.get(configuration.adapter_code)
    if adapter is None:
        raise ValueError(f"No adapter registered under code {configuration.adapter_code}.")
    status, message = adapter(electronic_invoice.payload)
    if status not in ("accepted", "rejected", "pending"):
        raise ValueError(f"Adapter returned an unsupported status {status}.")
    return Transmission.objects.create(
        electronic_invoice=electronic_invoice,
        adapter_code=configuration.adapter_code,
        idempotency_key=idempotency_key,
        status=status,
        provider_message=message[:500],
        provider_status=status,
    )


@transaction.atomic
def sync_provider_status(*, transmission_id: str, provider_status: str) -> tuple[Transmission, bool]:
    """Store the provider-side status and report whether it diverges from ours."""
    transmission = Transmission.objects.select_for_update().get(id=transmission_id)
    transmission.provider_status = provider_status
    transmission.status_checked_at = timezone.now()
    transmission.save(update_fields=["provider_status", "status_checked_at"])
    return transmission, provider_status != transmission.status
