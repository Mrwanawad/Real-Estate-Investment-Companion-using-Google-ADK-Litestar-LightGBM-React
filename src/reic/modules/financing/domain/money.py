"""Rounding and validation helpers shared by the financing calculators.

Conventions: every ``*_pct`` input is a fraction (0.10 means 10 percent), money is Decimal
quantized to the piastre (0.01 EGP) with ROUND_HALF_UP, rates are quantized to 6 decimals.
"""

from decimal import ROUND_HALF_UP, Decimal

from reic.modules.financing.domain.errors import FinancingValidationError

CENT = Decimal("0.01")
RATE_STEP = Decimal("0.000001")
ZERO = Decimal("0.00")


def q2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def q6(value: Decimal) -> Decimal:
    return value.quantize(RATE_STEP, rounding=ROUND_HALF_UP)


def from_float(value: float, step: Decimal) -> Decimal:
    return Decimal(repr(value)).quantize(step, rounding=ROUND_HALF_UP)


def require_finite(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise FinancingValidationError(f"{name} must be a finite number")


def require_positive(name: str, value: Decimal) -> None:
    require_finite(name, value)
    if value <= 0:
        raise FinancingValidationError(f"{name} must be greater than 0")


def require_fraction(name: str, value: Decimal) -> None:
    """Value must lie in [0, 1]; percentages are fractions, so 10 percent is 0.10."""
    require_finite(name, value)
    if value < 0 or value > 1:
        raise FinancingValidationError(
            f"{name} must be between 0 and 1 (a fraction, e.g. 0.10 for 10%), got {value}"
        )


def require_years(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 50:
        raise FinancingValidationError(f"{name} must be a whole number of years between 1 and 50")
