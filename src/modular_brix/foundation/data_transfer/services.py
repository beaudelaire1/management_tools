from collections.abc import Callable

from django.db import transaction

from .models import ExportJob, ImportJob, ImportRow

RowValidator = Callable[[dict], str | None]
RowApplier = Callable[[dict], None]
RowProvider = Callable[[str], list[dict]]


@transaction.atomic
def create_import_job(
    *,
    organization_id: str,
    label: str,
    rows: list[dict],
    all_or_nothing: bool = True,
) -> ImportJob:
    job = ImportJob.objects.create(
        organization_id=organization_id,
        label=label,
        all_or_nothing=all_or_nothing,
    )
    ImportRow.objects.bulk_create(
        [ImportRow(job=job, row_number=index + 1, payload=payload) for index, payload in enumerate(rows)]
    )
    return job


@transaction.atomic
def apply_import(*, job_id: str, validator: RowValidator, applier: RowApplier) -> ImportJob:
    """Validate every row first; in all-or-nothing mode no data is written if any row fails.

    A row-by-row report is always persisted on the rows themselves.
    """
    job = ImportJob.objects.select_for_update().get(id=job_id)
    rows = list(job.rows.order_by("row_number"))

    invalid_count = 0
    for row in rows:
        error = validator(row.payload)
        if error:
            row.status = "invalid"
            row.error = error
            invalid_count += 1
    if invalid_count and job.all_or_nothing:
        for row in rows:
            if row.status != "invalid":
                row.status = "skipped"
        ImportRow.objects.bulk_update(rows, ["status", "error"])
        job.status = "rejected"
        job.save(update_fields=["status"])
        return job

    for row in rows:
        if row.status == "invalid":
            continue
        applier(row.payload)
        row.status = "applied"
    ImportRow.objects.bulk_update(rows, ["status", "error"])
    job.status = "completed_with_errors" if invalid_count else "completed"
    job.save(update_fields=["status"])
    return job


@transaction.atomic
def run_export(*, organization_id: str, label: str, row_provider: RowProvider) -> tuple[ExportJob, list[dict]]:
    """The provider receives the organization id so exported data never crosses scopes."""
    job = ExportJob.objects.create(organization_id=organization_id, label=label)
    rows = row_provider(organization_id)
    job.row_count = len(rows)
    job.status = "completed"
    job.save(update_fields=["row_count", "status"])
    return job, rows


def apply_import_mapping(*, mapping_id: str, row: dict) -> dict:
    """Rename source columns to target fields; unmapped columns are dropped explicitly (F11)."""
    from .models import ImportMapping

    mapping = ImportMapping.objects.get(id=mapping_id)
    return {target: row[source] for source, target in mapping.field_map.items() if source in row}


def seal_export(*, payload: str, secret: str) -> str:
    """Integrity seal (HMAC-SHA256) over an export so tampering is detectable (F11).

    This is an authenticity seal, not confidentiality; encrypt transport and
    storage at the deployment layer.
    """
    import hashlib
    import hmac

    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_export_seal(*, payload: str, secret: str, seal: str) -> bool:
    import hmac

    return hmac.compare_digest(seal_export(payload=payload, secret=secret), seal)
