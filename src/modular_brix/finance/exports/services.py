import hashlib

from django.db import transaction

from modular_brix.finance.ledger.models import FiscalYear, JournalEntry

from .models import ExportIssue, FECExport

# Field order imposed by article A47 A-1 du LPF.
FEC_HEADER = (
    "JournalCode|JournalLib|EcritureNum|EcritureDate|CompteNum|CompteLib|CompAuxNum|CompAuxLib|"
    "PieceRef|PieceDate|EcritureLib|Debit|Credit|EcritureLet|DateLet|ValidDate|Montantdevise|Idevise"
)


def _fec_amount(value) -> str:
    return f"{value:.2f}".replace(".", ",")


@transaction.atomic
def generate_fec(*, organization_id: str, fiscal_year_id: str) -> FECExport:
    """Deterministic FEC: validated entries only, imposed column order, stable sorting,
    and a stored SHA-256 fingerprint tying the file to what was generated (spec C15)."""
    fiscal_year = FiscalYear.objects.get(id=fiscal_year_id, organization_id=organization_id)
    entries = (
        JournalEntry.objects.filter(
            organization_id=organization_id,
            status="validated",
            entry_date__gte=fiscal_year.starts_on,
            entry_date__lte=fiscal_year.ends_on,
        )
        .select_related("journal")
        .order_by("entry_date", "number")
    )
    lines = [FEC_HEADER]
    for entry in entries:
        valid_date = entry.validated_at.date().strftime("%Y%m%d")
        for line in entry.lines.select_related("account").order_by("position"):
            lines.append(
                "|".join(
                    [
                        entry.journal.code,
                        entry.journal.label,
                        entry.number,
                        entry.entry_date.strftime("%Y%m%d"),
                        line.account.code,
                        line.account.label,
                        "",  # CompAuxNum: subledger account, C09 linkage to come
                        "",  # CompAuxLib
                        entry.reference,
                        entry.entry_date.strftime("%Y%m%d"),
                        line.label or entry.label,
                        _fec_amount(line.debit),
                        _fec_amount(line.credit),
                        "",  # EcritureLet
                        "",  # DateLet
                        valid_date,
                        "",  # Montantdevise
                        "",  # Idevise
                    ]
                )
            )
    content = "\r\n".join(lines) + "\r\n"
    export = FECExport.objects.create(
        organization_id=organization_id,
        fiscal_year=fiscal_year,
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    _run_controls(export, list(entries))
    return export


def _run_controls(export: FECExport, entries: list[JournalEntry]) -> None:
    """Sequence and journal controls; anomalies are recorded, never silently dropped."""
    if not entries:
        ExportIssue.objects.create(
            export=export, severity="warning", message="No validated entry in the fiscal year."
        )
        return
    by_journal: dict[str, list[str]] = {}
    for entry in entries:
        by_journal.setdefault(entry.journal.code, []).append(entry.number)
    for journal_code, numbers in by_journal.items():
        sequence_numbers = sorted(int(number.rsplit("-", 1)[-1]) for number in numbers)
        expected = list(range(sequence_numbers[0], sequence_numbers[0] + len(sequence_numbers)))
        if sequence_numbers != expected:
            ExportIssue.objects.create(
                export=export,
                severity="error",
                message=f"Journal {journal_code} has a broken entry-number sequence.",
            )
