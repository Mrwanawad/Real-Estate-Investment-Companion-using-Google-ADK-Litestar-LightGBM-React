"""PV / NPV / IRR wrappers over numpy-financial with Decimal at the boundaries.

Cash flows are monthly with index 0 first (numpy-financial convention: the flow at index t is
discounted by (1+r)^t, so index 0 is not discounted). Annual discount rates are converted to
monthly with (1+r)^(1/12) - 1. Money results are quantized to 0.01, rates to 6 decimals.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal

import numpy as np
import numpy_financial as npf

from reic.modules.financing.domain.errors import FinancingValidationError
from reic.modules.financing.domain.money import (
    CENT,
    RATE_STEP,
    ZERO,
    from_float,
    require_finite,
)


def monthly_rate(annual_rate: Decimal) -> float:
    """Effective monthly rate equivalent to an effective annual rate: (1+r)^(1/12) - 1."""
    require_finite("annual_rate", annual_rate)
    if annual_rate <= -1:
        raise FinancingValidationError("annual_rate must be greater than -1")
    return float((1 + annual_rate) ** (Decimal(1) / 12) - 1)


def npv_periodic(rate: float, flows: Sequence[Decimal]) -> Decimal:
    """NPV with a per-period rate, flow at index 0 undiscounted. Exact when rate is 0."""
    if not flows:
        raise FinancingValidationError("cash flows must not be empty")
    if rate == 0:
        return sum(flows, ZERO).quantize(CENT)
    return from_float(float(npf.npv(rate, [float(f) for f in flows])), CENT)


def npv(annual_rate: Decimal, flows: Sequence[Decimal]) -> Decimal:
    """NPV of monthly flows (index 0 first) at an annual discount rate."""
    return npv_periodic(monthly_rate(annual_rate), flows)


def pv(annual_rate: Decimal, flows_by_month: Mapping[int, Decimal]) -> Decimal:
    """Present value at month 0 of sparse flows keyed by month offset."""
    if not flows_by_month:
        raise FinancingValidationError("cash flows must not be empty")
    if min(flows_by_month) < 0:
        raise FinancingValidationError("month offsets must not be negative")
    dense = [ZERO] * (max(flows_by_month) + 1)
    for month, amount in flows_by_month.items():
        dense[month] += amount
    return npv(annual_rate, dense)


def annualize(monthly: Decimal) -> Decimal:
    """Effective annual rate from an effective monthly rate."""
    return from_float(float((1 + monthly) ** 12 - 1), RATE_STEP)


def irr(flows: Sequence[Decimal], *, annualized: bool = False) -> Decimal | None:
    """Per-period IRR (monthly for monthly flows) to 6dp; None if there is no sign change or
    numpy-financial finds no real root."""
    values = [float(f) for f in flows]
    if not (any(v > 0 for v in values) and any(v < 0 for v in values)):
        return None
    with np.errstate(all="ignore"):
        result = float(npf.irr(values))
    if np.isnan(result):
        return None
    rate = from_float(result, RATE_STEP)
    return annualize(rate) if annualized else rate
