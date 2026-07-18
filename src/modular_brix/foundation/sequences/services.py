from django.db import IntegrityError, transaction

from .models import SequenceCounter


@transaction.atomic
def allocate_number(*, organization_id: str, code: str, period: str) -> int:
    """Allocate the next number for a sequence scope, atomically and without gaps.

    The counter row is locked (SELECT FOR UPDATE) so concurrent allocations
    serialize and can never produce duplicates.
    """
    try:
        with transaction.atomic():
            SequenceCounter.objects.get_or_create(
                organization_id=organization_id,
                code=code,
                period=period,
            )
    except IntegrityError:
        pass  # Another transaction created the counter concurrently.

    counter = SequenceCounter.objects.select_for_update().get(
        organization_id=organization_id,
        code=code,
        period=period,
    )
    counter.last_number += 1
    counter.save(update_fields=["last_number", "updated_at"])
    return counter.last_number


def format_reference(*, prefix: str, period: str, number: int, width: int = 6) -> str:
    return f"{prefix}-{period}-{number:0{width}d}"
