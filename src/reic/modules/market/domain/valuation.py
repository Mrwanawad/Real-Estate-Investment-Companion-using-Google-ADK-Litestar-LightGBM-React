"""Pure valuation helpers: baseline model, quantile combination, holdout split, month maths."""

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from reic.modules.market.domain.metrics import quantile
from reic.modules.market.domain.models import Quantiles, UnitFeatures


def combine_value_and_growth(value: Quantiles, growth: Quantiles) -> Quantiles:
    """Quantiles of value x growth, treating both as independent and log-normal per side.

    Multiplying p10 by p10 would describe a joint ~1% tail and overstate the range. Instead each
    side's log half-width (a multiple of sigma) adds in quadrature with the other input's, and the
    median is p50_value x p50_growth. Lower and upper sides are combined separately so skew in
    either input survives.
    """
    value, growth = value.ordered(), growth.ordered()
    median = value.p50 * growth.p50
    down = math.hypot(math.log(value.p50 / value.p10), math.log(growth.p50 / growth.p10))
    up = math.hypot(math.log(value.p90 / value.p50), math.log(growth.p90 / growth.p50))
    return Quantiles(median * math.exp(-down), median, median * math.exp(up))


def conformal_log_margin(
    preds: Sequence[Quantiles], actual: Sequence[float], coverage: float
) -> float:
    """Split-conformal quantile regression margin (Romano et al. 2019), in log space.

    Score = how far the actual falls outside [p10, p90] in log units (negative when inside).
    Widening both bounds by the ceil((n+1)*coverage)-th smallest score gives finite-sample
    coverage >= `coverage` on exchangeable data. A negative margin narrows the band.
    """
    scores = sorted(
        max(math.log(q.p10 / y), math.log(y / q.p90)) for q, y in zip(preds, actual, strict=True)
    )
    if not scores:
        raise ValueError("calibration set is empty")
    k = min(len(scores), math.ceil((len(scores) + 1) * coverage))
    return scores[k - 1]


def widen(q: Quantiles, log_margin: float) -> Quantiles:
    return Quantiles(q.p10 * math.exp(-log_margin), q.p50, q.p90 * math.exp(log_margin)).ordered()


class AreaMedianBaseline:
    """Baseline unit value: empirical P10/P50/P90 of price per m2 in the unit's area."""

    name = "baseline"

    def __init__(self) -> None:
        self._by_area: dict[str, Quantiles] = {}
        self._overall: Quantiles | None = None

    def fit(self, features: Sequence[UnitFeatures], ppm2: Sequence[float]) -> None:
        groups: dict[str, list[float]] = defaultdict(list)
        for f, y in zip(features, ppm2, strict=True):
            groups[f.area_id].append(y)
        self._by_area = {a: _q3(v) for a, v in groups.items()}
        self._overall = _q3(list(ppm2))

    def predict(self, features: Sequence[UnitFeatures]) -> list[Quantiles]:
        if self._overall is None:
            raise RuntimeError("baseline is not fitted")
        return [self._by_area.get(f.area_id, self._overall) for f in features]


def _q3(values: Sequence[float]) -> Quantiles:
    return Quantiles(quantile(values, 0.1), quantile(values, 0.5), quantile(values, 0.9))


def holdout_split(n: int, test_fraction: float, seed: int) -> tuple[list[int], list[int]]:
    """Deterministic shuffled split of range(n) into (train, test) index lists."""
    idx = list(range(n))
    random.Random(seed).shuffle(idx)
    cut = round(n * test_fraction)
    return sorted(idx[cut:]), sorted(idx[:cut])


def add_months(month: date, n: int) -> date:
    total = month.year * 12 + month.month - 1 + n
    return date(total // 12, total % 12 + 1, 1)
