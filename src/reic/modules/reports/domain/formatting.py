from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def to_float(value: Any) -> float | None:
    """Numbers, Decimals and numeric strings ('1,250,000.50') to float; anything else to None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    try:
        return float(Decimal(str(value).replace(",", "").strip()))
    except (InvalidOperation, ValueError):
        return None


def money(value: Any) -> str:
    """Whole EGP with thousands separators (Latin digits). Unparseable input is shown as is."""
    number = to_float(value)
    if number is None:
        return "-" if value in (None, "") else str(value)
    return f"{int(Decimal(str(number)).quantize(Decimal(1), rounding=ROUND_HALF_UP)):,}"


def compact_money(number: float) -> str:
    """Short axis label: 1.2M, 850K."""
    size = abs(number)
    if size >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if size >= 1_000:
        return f"{number / 1_000:.0f}K"
    return f"{number:.0f}"


def percent(value: Any, digits: int = 1) -> str:
    """Fractions up to 1.5 (0.082) are read as ratios and shown as 8.2%; larger values are
    taken as already in percent."""
    number = to_float(value)
    if number is None:
        return "-" if value in (None, "") else str(value)
    if abs(number) <= 1.5:
        number *= 100
    return f"{number:.{digits}f}%"


def plain(value: Any) -> str:
    return "-" if value in (None, "") else str(value).replace("_", " ")
