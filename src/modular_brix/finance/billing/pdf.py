"""Regulatory invoice PDF rendering (spec C01).

Rendering is deliberately strict: it refuses drafts and any invoice whose
mandatory-mention snapshot is incomplete, so a PDF handed to a customer always
carries the full French mention set. Amounts reuse `modular_brix.common.money`
so the PDF can never disagree with the stored totals.
"""

from decimal import Decimal

from modular_brix.common.money import round_money
from modular_brix.common.pdf import A4_HEIGHT, PdfPage, PdfWriter

from .models import Invoice
from .services import missing_mandatory_mentions

_LEFT = 50
_RIGHT_COLUMN = 320
_BOTTOM_MARGIN = 90
_LINE_HEIGHT = 14
_TABLE_COLUMNS = (
    (_LEFT, "Désignation"),
    (330, "Qté"),
    (390, "PU HT"),
    (460, "TVA %"),
    (510, "Total HT"),
)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _table_header(page: PdfPage, y: float) -> float:
    for x, label in _TABLE_COLUMNS:
        page.text(x, y, label, size=9, bold=True)
    return y - _LINE_HEIGHT


def _vat_breakdown(invoice: Invoice) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Per-rate (rate, base, tax) rows using the same per-line rounding as the totals."""
    buckets: dict[Decimal, list[Decimal]] = {}
    for line in invoice.lines.order_by("position"):
        base = round_money(Decimal(line.quantity) * Decimal(line.unit_price))
        tax = round_money(base * Decimal(line.tax_rate) / Decimal("100"))
        rate = Decimal(line.tax_rate)
        bucket = buckets.setdefault(rate, [Decimal("0.00"), Decimal("0.00")])
        bucket[0] += base
        bucket[1] += tax
    return [(rate, base, tax) for rate, (base, tax) in sorted(buckets.items())]


def render_invoice_pdf(*, invoice_id: str) -> bytes:
    invoice = Invoice.objects.select_related("organization", "party").get(id=invoice_id)
    if invoice.status != "issued":
        raise ValueError("Only an issued invoice can be rendered as a PDF.")
    missing = missing_mandatory_mentions(invoice)
    if missing:
        raise ValueError("Cannot render the invoice PDF; missing mandatory mentions: " + ", ".join(missing))

    writer = PdfWriter()
    page = writer.add_page()
    y: float = A4_HEIGHT - 60

    page.text(_LEFT, y, f"FACTURE {invoice.number}", size=16, bold=True)
    y -= 2 * _LINE_HEIGHT
    page.text(_LEFT, y, f"Date d'émission : {invoice.issue_date.isoformat()}", size=10)
    page.text(_RIGHT_COLUMN, y, f"Date d'échéance : {invoice.due_date.isoformat()}", size=10)
    y -= 2 * _LINE_HEIGHT

    seller_lines = [
        (invoice.seller_name, True),
        (invoice.seller_address, False),
        (f"Identifiant légal : {invoice.seller_legal_identifier}", False),
    ]
    if invoice.seller_legal_form or invoice.seller_share_capital:
        detail = " - ".join(
            part
            for part in (
                invoice.seller_legal_form,
                f"Capital social : {invoice.seller_share_capital}" if invoice.seller_share_capital else "",
            )
            if part
        )
        seller_lines.append((detail, False))
    if invoice.seller_registry_city:
        seller_lines.append((f"RCS {invoice.seller_registry_city}", False))
    if invoice.seller_vat_number:
        seller_lines.append((f"N° TVA intracommunautaire : {invoice.seller_vat_number}", False))
    buyer_lines = [(invoice.buyer_name, True), (invoice.buyer_address, False)]
    if invoice.buyer_vat_number:
        buyer_lines.append((f"N° TVA acheteur : {invoice.buyer_vat_number}", False))

    block_top = y
    for text, bold in seller_lines:
        page.text(_LEFT, y, text, size=9, bold=bold)
        y -= _LINE_HEIGHT
    buyer_y = block_top
    for text, bold in buyer_lines:
        page.text(_RIGHT_COLUMN, buyer_y, text, size=9, bold=bold)
        buyer_y -= _LINE_HEIGHT
    y = min(y, buyer_y) - _LINE_HEIGHT

    y = _table_header(page, y)
    for line in invoice.lines.order_by("position"):
        if y < _BOTTOM_MARGIN:
            page = writer.add_page()
            y = _table_header(page, A4_HEIGHT - 60)
        base = round_money(Decimal(line.quantity) * Decimal(line.unit_price))
        page.text(_LEFT, y, line.description[:52], size=9)
        page.text(330, y, f"{line.quantity:.3f}", size=9)
        page.text(390, y, f"{line.unit_price:.4f}", size=9)
        page.text(460, y, f"{line.tax_rate:.2f}", size=9)
        page.text(510, y, _money(base), size=9)
        y -= _LINE_HEIGHT

    footer = [
        ("", False),
        (f"Total HT : {_money(invoice.total_excl_tax)} {invoice.currency}", False),
    ]
    footer.extend(
        (f"TVA {rate:.2f} % sur {_money(base)} : {_money(tax)} {invoice.currency}", False)
        for rate, base, tax in _vat_breakdown(invoice)
    )
    footer.extend(
        [
            (f"Total TVA : {_money(invoice.total_tax)} {invoice.currency}", False),
            (f"Total TTC : {_money(invoice.total_incl_tax)} {invoice.currency}", True),
            ("", False),
            (f"Pénalités de retard : {invoice.late_penalty_rate:.3f} % (taux annuel)", False),
            (
                "Indemnité forfaitaire pour frais de recouvrement : "
                f"{_money(invoice.recovery_indemnity)} {invoice.currency}",
                False,
            ),
            (invoice.early_discount_terms, False),
        ]
    )
    if invoice.vat_exemption_mention:
        footer.append((invoice.vat_exemption_mention, False))
    for text, bold in footer:
        if y < _BOTTOM_MARGIN - 2 * _LINE_HEIGHT:
            page = writer.add_page()
            y = A4_HEIGHT - 60
        if text:
            page.text(_LEFT, y, text, size=9, bold=bold)
        y -= _LINE_HEIGHT

    return writer.render()
