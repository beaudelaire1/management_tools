"""Centralized monetary computation: single source of truth for totals and rounding.

Every surface (service, API, PDF, export) must use these helpers so the same
lines always produce the same amounts (spec invariant 11.2).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Totals:
    excl_tax: Decimal
    tax: Decimal
    incl_tax: Decimal


def compute_totals(lines) -> Totals:
    """Compute document totals from line objects exposing quantity, unit_price, tax_rate (%).

    Rounding is applied per line, then summed, deterministically.
    """
    excl_tax = Decimal("0.00")
    tax = Decimal("0.00")
    for line in lines:
        line_excl = round_money(Decimal(line.quantity) * Decimal(line.unit_price))
        line_tax = round_money(line_excl * Decimal(line.tax_rate) / Decimal("100"))
        excl_tax += line_excl
        tax += line_tax
    return Totals(excl_tax=excl_tax, tax=tax, incl_tax=excl_tax + tax)
