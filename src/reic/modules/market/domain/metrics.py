"""Pure-Python forecast and regression metrics. Fractions, not percent (0.05 = 5%)."""

import math
from collections.abc import Mapping, Sequence


def _check(actual: Sequence[float], *others: Sequence[float]) -> None:
    if not actual:
        raise ValueError("metrics need at least one point")
    if any(len(o) != len(actual) for o in others):
        raise ValueError("length mismatch")


def mae(actual: Sequence[float], pred: Sequence[float]) -> float:
    _check(actual, pred)
    return sum(abs(a - p) for a, p in zip(actual, pred, strict=True)) / len(actual)


def mape(actual: Sequence[float], pred: Sequence[float]) -> float:
    _check(actual, pred)
    if any(a == 0 for a in actual):
        raise ValueError("MAPE undefined for zero actuals")
    return sum(abs(a - p) / abs(a) for a, p in zip(actual, pred, strict=True)) / len(actual)


def seasonal_naive_scale(train: Sequence[float], season: int = 12) -> float:
    """In-sample MAE of the seasonal naive forecast: the MASE denominator."""
    if len(train) <= season:
        raise ValueError("training series shorter than one season")
    diffs = [abs(train[i] - train[i - season]) for i in range(season, len(train))]
    return sum(diffs) / len(diffs)


def mase(
    actual: Sequence[float], pred: Sequence[float], train: Sequence[float], season: int = 12
) -> float:
    scale = seasonal_naive_scale(train, season)
    if scale == 0:
        raise ValueError("MASE undefined for a constant training series")
    return mae(actual, pred) / scale


def coverage(actual: Sequence[float], lower: Sequence[float], upper: Sequence[float]) -> float:
    _check(actual, lower, upper)
    inside = sum(lo <= a <= hi for a, lo, hi in zip(actual, lower, upper, strict=True))
    return inside / len(actual)


def pinball(actual: Sequence[float], pred: Sequence[float], q: float) -> float:
    _check(actual, pred)
    total = 0.0
    for a, p in zip(actual, pred, strict=True):
        diff = a - p
        total += max(q * diff, (q - 1) * diff)
    return total / len(actual)


def mean_pinball(actual: Sequence[float], preds: Mapping[float, Sequence[float]]) -> float:
    """Average pinball loss over the given quantile levels."""
    return sum(pinball(actual, p, q) for q, p in preds.items()) / len(preds)


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (numpy's default method)."""
    if not values:
        raise ValueError("quantile of empty sequence")
    xs = sorted(values)
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def annualised(ratio: float, months: int) -> float:
    """Compound annual growth rate for a total growth `ratio` over `months`."""
    if ratio <= 0 or months <= 0:
        raise ValueError("ratio and months must be positive")
    return ratio ** (12 / months) - 1


def annual_log_return_vol(levels: Sequence[float]) -> float:
    """Sample std of non-overlapping 12-month log returns, anchored on the latest month."""
    returns = [math.log(levels[i] / levels[i - 12]) for i in range(len(levels) - 1, 11, -12)]
    if len(returns) < 2:
        raise ValueError("need at least 25 months for an annual volatility")
    mean = sum(returns) / len(returns)
    return math.sqrt(sum((r - mean) ** 2 for r in returns) / (len(returns) - 1))
