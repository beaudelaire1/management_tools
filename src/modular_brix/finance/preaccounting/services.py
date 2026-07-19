import hashlib
from datetime import date

from django.db import transaction
from django.utils import timezone

from modular_brix.finance.billing.models import Invoice
from modular_brix.finance.payments.models import Payment

from .models import LOCKED_BATCH_ERROR, AccountantComment, AccountingMapping, PreAccountingItem, TransmissionBatch


def mapping_for(*, organization_id: str, source_kind: str, on_day: date) -> str:
    mapping = (
        AccountingMapping.objects.filter(
            organization_id=organization_id, source_kind=source_kind, valid_from__lte=on_day
        )
        .order_by("-valid_from")
        .first()
    )
    if mapping is None:
        raise ValueError(f"No accounting mapping effective for {source_kind} on {on_day}.")
    return mapping.account_code


@transaction.atomic
def build_batch(*, organization_id: str, period_start: date, period_end: date) -> TransmissionBatch:
    """Deterministic batch: the same period always rebuilds to the same content hash.

    A transmitted batch for the period locks it; corrections require a new period batch.
    """
    locked = TransmissionBatch.objects.filter(
        organization_id=organization_id,
        period_start=period_start,
        period_end=period_end,
        status="transmitted",
    ).exists()
    if locked:
        raise ValueError(LOCKED_BATCH_ERROR)
    batch = TransmissionBatch.objects.create(
        organization_id=organization_id, period_start=period_start, period_end=period_end
    )
    position = 0
    digest = hashlib.sha256()
    invoices = Invoice.objects.filter(
        organization_id=organization_id,
        status="issued",
        issue_date__gte=period_start,
        issue_date__lte=period_end,
    ).order_by("number")
    for invoice in invoices:
        position += 1
        account = mapping_for(
            organization_id=organization_id, source_kind="sales_invoice", on_day=invoice.issue_date
        )
        item = PreAccountingItem.objects.create(
            batch=batch,
            position=position,
            source_kind="sales_invoice",
            source_id=str(invoice.id),
            account_code=account,
            label=f"Facture {invoice.number}",
            credit=invoice.total_incl_tax,
        )
        digest.update(f"{item.source_kind}:{invoice.number}:{item.credit}:{account}".encode())
    payments = Payment.objects.filter(
        organization_id=organization_id,
        received_at__date__gte=period_start,
        received_at__date__lte=period_end,
    ).order_by("received_at", "id")
    for payment in payments:
        position += 1
        account = mapping_for(
            organization_id=organization_id, source_kind="customer_payment", on_day=payment.received_at.date()
        )
        item = PreAccountingItem.objects.create(
            batch=batch,
            position=position,
            source_kind="customer_payment",
            source_id=str(payment.id),
            account_code=account,
            label=f"Règlement {payment.provider_reference or payment.id}",
            debit=payment.amount,
        )
        digest.update(f"{item.source_kind}:{payment.id}:{item.debit}:{account}".encode())
    batch.content_hash = digest.hexdigest()
    batch.save(update_fields=["content_hash"])
    return batch


@transaction.atomic
def transmit_batch(*, batch_id: str) -> TransmissionBatch:
    batch = TransmissionBatch.objects.select_for_update().get(id=batch_id)
    if batch.status != "draft":
        raise ValueError("Only a draft batch can be transmitted.")
    if not batch.items.exists():
        raise ValueError("An empty batch cannot be transmitted.")
    batch.status = "transmitted"
    batch.save(update_fields=["status"])
    return batch


@transaction.atomic
def add_comment(*, batch_id: str, author_name: str, body: str) -> AccountantComment:
    return AccountantComment.objects.create(batch_id=batch_id, author_name=author_name, body=body)


@transaction.atomic
def resolve_comment(*, comment_id: str) -> AccountantComment:
    comment = AccountantComment.objects.select_for_update().get(id=comment_id)
    if comment.resolved_at is not None:
        raise ValueError("This comment is already resolved.")
    comment.resolved_at = timezone.now()
    comment.save(update_fields=["resolved_at"])
    return comment


def missing_documents(*, batch_id: str) -> list[PreAccountingItem]:
    """Invoice items whose source no longer resolves are flagged, never silently dropped."""
    batch = TransmissionBatch.objects.get(id=batch_id)
    missing = []
    for item in batch.items.filter(source_kind="sales_invoice"):
        if not Invoice.objects.filter(id=item.source_id).exists():
            missing.append(item)
    return missing
