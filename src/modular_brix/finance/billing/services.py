from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modular_brix.common.money import compute_totals
from modular_brix.foundation.sequences.services import allocate_number, format_reference
from modular_brix.management.sales.models import SalesOrder

from .models import CreditNote, Invoice, InvoiceLine


@transaction.atomic
def create_invoice_from_order(*, order_id: str) -> Invoice:
    """Idempotent conversion: the same order always yields the same single invoice."""
    order = SalesOrder.objects.select_for_update().select_related("party", "organization").get(id=order_id)
    if order.party.organization_id != order.organization_id:
        raise ValueError("An invoice source order and its party must belong to the same organization.")
    existing = Invoice.objects.filter(sales_order=order).first()
    if existing is not None:
        return existing

    invoice = Invoice.objects.create(
        organization_id=order.organization_id,
        party_id=order.party_id,
        sales_order=order,
        currency=order.currency,
    )
    for line in order.lines.order_by("position"):
        InvoiceLine.objects.create(
            invoice=invoice,
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
        )
    return invoice


# Fixed recovery indemnity for professional late payment (art. D441-5 du code de commerce).
LEGAL_RECOVERY_INDEMNITY_EUR = Decimal("40.00")
DEFAULT_EARLY_DISCOUNT_TERMS = "Escompte pour paiement anticipé : néant"
VAT_FRANCHISE_MENTION = "TVA non applicable, art. 293 B du CGI"


def _format_address(address) -> str:
    parts = [address.line_1, address.line_2, f"{address.postal_code} {address.city}", address.country_code]
    return ", ".join(part for part in parts if part)


def _seller_snapshot(organization) -> dict[str, str]:
    """Collect the seller-side mandatory mentions available on the organization (F01)."""
    snapshot = {
        "seller_legal_identifier": organization.legal_identifier,
        "seller_legal_form": "",
        "seller_share_capital": "",
        "seller_registry_city": "",
        "seller_vat_number": "",
        "seller_address": "",
        "vat_exemption_mention": "",
    }
    entity = organization.legal_entities.filter(is_active=True).order_by("name").first()
    if entity is not None:
        snapshot["seller_legal_form"] = entity.legal_form
    profile = getattr(organization, "legal_profile", None)
    if profile is not None:
        snapshot["seller_share_capital"] = profile.share_capital
        snapshot["seller_registry_city"] = profile.registry_city
    fiscal = getattr(organization, "fiscal_profile", None)
    if fiscal is not None:
        snapshot["seller_vat_number"] = fiscal.vat_number
        if "franchise" in fiscal.fiscal_regime.lower():
            snapshot["vat_exemption_mention"] = VAT_FRANCHISE_MENTION
    addresses = organization.addresses.filter(is_active=True)
    address = addresses.filter(address_type="billing").first() or addresses.first()
    if address is not None:
        snapshot["seller_address"] = _format_address(address)
    return snapshot


def _buyer_identifier(party, scheme: str) -> str:
    identifier = party.identifiers.filter(scheme=scheme).order_by("value").first()
    return identifier.value if identifier is not None else ""


def _buyer_address(party) -> str:
    addresses = party.addresses.filter(is_active=True)
    address = addresses.filter(address_type="billing").first() or addresses.first()
    return _format_address(address) if address is not None else ""


@transaction.atomic
def issue_invoice(
    *,
    invoice_id: str,
    payment_term_days: int = 30,
    buyer_address: str = "",
    late_penalty_rate: Decimal | None = None,
    recovery_indemnity: Decimal | None = LEGAL_RECOVERY_INDEMNITY_EUR,
    early_discount_terms: str = DEFAULT_EARLY_DISCOUNT_TERMS,
) -> Invoice:
    """Issuance is irreversible: chronological number, frozen snapshots and totals.

    The mandatory-mention snapshot (spec C01) is frozen from the organization's
    legal and fiscal profiles and from the caller-provided payment terms; gaps
    are reported by `missing_mandatory_mentions` and block PDF rendering only,
    so baseline flows keep working while compliance is completed per tenant.
    """
    invoice = Invoice.objects.select_for_update().select_related("organization", "party").get(id=invoice_id)
    if invoice.status != "draft":
        raise ValueError("Only a draft invoice can be issued.")
    if not invoice.lines.exists():
        raise ValueError("An empty invoice cannot be issued.")

    today = timezone.now().date()
    year = str(today.year)
    number = allocate_number(organization_id=str(invoice.organization_id), code="invoice", period=year)
    totals = compute_totals(invoice.lines.all())

    invoice.number = format_reference(prefix="INV", period=year, number=number)
    invoice.status = "issued"
    invoice.issue_date = today
    invoice.due_date = today + timedelta(days=payment_term_days)
    invoice.seller_name = invoice.organization.legal_name
    invoice.buyer_name = invoice.party.display_name
    for field, value in _seller_snapshot(invoice.organization).items():
        setattr(invoice, field, value)
    invoice.buyer_address = buyer_address.strip() or _buyer_address(invoice.party)
    invoice.buyer_vat_number = _buyer_identifier(invoice.party, "vat")
    invoice.late_penalty_rate = late_penalty_rate
    invoice.recovery_indemnity = recovery_indemnity
    invoice.early_discount_terms = early_discount_terms.strip()
    invoice.total_excl_tax = totals.excl_tax
    invoice.total_tax = totals.tax
    invoice.total_incl_tax = totals.incl_tax
    invoice.save()
    return invoice


def missing_mandatory_mentions(invoice: Invoice) -> list[str]:
    """Return the mandatory mentions (spec C01) absent from an invoice snapshot.

    The seller VAT number is only required when no VAT exemption mention
    applies; every other listed mention is unconditional for a French invoice.
    """
    required_fields = {
        "number": invoice.number,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "seller_name": invoice.seller_name,
        "seller_legal_identifier": invoice.seller_legal_identifier,
        "seller_address": invoice.seller_address,
        "buyer_name": invoice.buyer_name,
        "buyer_address": invoice.buyer_address,
        "late_penalty_rate": invoice.late_penalty_rate,
        "recovery_indemnity": invoice.recovery_indemnity,
        "early_discount_terms": invoice.early_discount_terms,
        "total_excl_tax": invoice.total_excl_tax,
        "total_tax": invoice.total_tax,
        "total_incl_tax": invoice.total_incl_tax,
    }
    missing = [name for name, value in required_fields.items() if value in ("", None)]
    if not invoice.seller_vat_number and not invoice.vat_exemption_mention:
        missing.append("seller_vat_number")
    if not invoice.lines.exists():
        missing.append("lines")
    return missing


def credited_amount(invoice: Invoice) -> Decimal:
    return invoice.credit_notes.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def allocated_amount(invoice: Invoice) -> Decimal:
    total = invoice.allocations.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0.00")


def invoice_remaining(invoice: Invoice) -> Decimal:
    """Remaining due = issued total - credit notes - payment allocations."""
    if invoice.status != "issued":
        raise ValueError("Balance is only defined for an issued invoice.")
    return invoice.total_incl_tax - credited_amount(invoice) - allocated_amount(invoice)


@transaction.atomic
def create_credit_note(*, invoice_id: str, amount: Decimal, reason: str) -> CreditNote:
    """A credit note can never exceed what remains creditable on the invoice (spec 11.2)."""
    invoice = Invoice.objects.select_for_update().get(id=invoice_id)
    if invoice.status != "issued":
        raise ValueError("Credit notes only apply to issued invoices.")
    if amount <= 0:
        raise ValueError("Credit note amount must be positive.")
    if not reason.strip():
        raise ValueError("A credit note reason is required.")

    creditable = invoice.total_incl_tax - credited_amount(invoice)
    if amount > creditable:
        raise ValueError(f"Credit note amount {amount} exceeds creditable remainder {creditable}.")

    year = str(timezone.now().year)
    number = allocate_number(organization_id=str(invoice.organization_id), code="credit-note", period=year)
    return CreditNote.objects.create(
        invoice=invoice,
        number=format_reference(prefix="CN", period=year, number=number),
        amount=amount,
        reason=reason.strip(),
    )
