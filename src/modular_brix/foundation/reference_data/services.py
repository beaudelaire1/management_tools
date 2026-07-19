from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import Country, Currency, PaymentTerm, TaxCode, Unit

INITIAL_COUNTRIES = [("FR", "France"), ("BE", "Belgique"), ("IT", "Italia"), ("DE", "Deutschland")]
INITIAL_CURRENCIES = [("EUR", "Euro", 2), ("USD", "US Dollar", 2), ("CHF", "Swiss Franc", 2)]
INITIAL_UNITS = [("unit", "Unité"), ("hour", "Heure"), ("day", "Jour"), ("kg", "Kilogramme")]
INITIAL_TAX_CODES = [
    ("fr-standard", "TVA taux normal", Decimal("20.000"), date(2014, 1, 1)),
    ("fr-intermediate", "TVA taux intermédiaire", Decimal("10.000"), date(2014, 1, 1)),
    ("fr-reduced", "TVA taux réduit", Decimal("5.500"), date(2014, 1, 1)),
    ("fr-super-reduced", "TVA taux particulier", Decimal("2.100"), date(2014, 1, 1)),
]
INITIAL_PAYMENT_TERMS = [("immediate", "Comptant", 0), ("net-30", "30 jours", 30), ("net-45", "45 jours", 45)]


@transaction.atomic
def load_initial_reference_data() -> dict[str, int]:
    """Idempotent initial load: running it twice yields the exact same referential."""
    for iso2, name in INITIAL_COUNTRIES:
        Country.objects.get_or_create(iso2=iso2, defaults={"name": name})
    for iso3, name, decimals in INITIAL_CURRENCIES:
        Currency.objects.get_or_create(iso3=iso3, defaults={"name": name, "decimal_places": decimals})
    for code, label in INITIAL_UNITS:
        Unit.objects.get_or_create(code=code, defaults={"label": label})
    for code, label, rate, valid_from in INITIAL_TAX_CODES:
        TaxCode.objects.get_or_create(code=code, valid_from=valid_from, defaults={"label": label, "rate": rate})
    for code, label, days in INITIAL_PAYMENT_TERMS:
        PaymentTerm.objects.get_or_create(code=code, defaults={"label": label, "days": days})

    return {
        "countries": Country.objects.count(),
        "currencies": Currency.objects.count(),
        "units": Unit.objects.count(),
        "tax_codes": TaxCode.objects.count(),
        "payment_terms": PaymentTerm.objects.count(),
    }


def current_tax_code(*, code: str, on_date: date) -> TaxCode | None:
    """Expired values are never proposed, but history stays readable via the model."""
    from django.db import models as dj_models

    return (
        TaxCode.objects.filter(code=code, is_active=True, valid_from__lte=on_date)
        .filter(dj_models.Q(valid_to__isnull=True) | dj_models.Q(valid_to__gte=on_date))
        .order_by("-valid_from")
        .first()
    )


def is_business_day(*, organization_id: str, day) -> bool:
    """Weekends and listed holidays are non-working (F10)."""
    from .models import Holiday

    if day.weekday() >= 5:
        return False
    return not Holiday.objects.filter(calendar__organization_id=organization_id, day=day).exists()


def add_business_days(*, organization_id: str, start, days: int):
    """Deadline computation that skips weekends and holidays (F10)."""
    from datetime import timedelta

    if days < 0:
        raise ValueError("Business-day offsets are forward only.")
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if is_business_day(organization_id=organization_id, day=current):
            remaining -= 1
    return current
