import math
from datetime import date

import pytest

from reic.modules.market.domain import metrics as m
from reic.modules.market.domain.models import IndexSeries, Quantiles
from reic.modules.market.domain.valuation import (
    add_months,
    combine_value_and_growth,
    conformal_log_margin,
    holdout_split,
    widen,
)


def test_mae_mape() -> None:
    assert m.mae([100, 200], [110, 180]) == 15
    assert m.mape([100, 200], [110, 180]) == pytest.approx(0.1)
    with pytest.raises(ValueError):
        m.mape([0, 1], [1, 1])


def test_mase_uses_seasonal_naive_scale() -> None:
    train = [float(i) for i in range(24)]  # seasonal diff is always 12
    assert m.seasonal_naive_scale(train, 12) == 12
    assert m.mase([30, 30], [24, 36], train, 12) == pytest.approx(0.5)


def test_coverage_and_pinball() -> None:
    assert m.coverage([1, 5, 10], [0, 6, 9], [2, 7, 11]) == pytest.approx(2 / 3)
    # under-forecast by 10 at q=0.9 costs 9; over-forecast by 10 costs 1
    assert m.pinball([100], [90], 0.9) == pytest.approx(9)
    assert m.pinball([100], [110], 0.9) == pytest.approx(1)
    assert m.mean_pinball([100], {0.1: [90], 0.9: [90]}) == pytest.approx((1 + 9) / 2)


def test_quantile_matches_numpy_linear() -> None:
    assert m.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert m.quantile([5, 1, 3], 0.1) == pytest.approx(1.4)


def test_annualised_and_volatility() -> None:
    assert m.annualised(1.21, 24) == pytest.approx(0.1)
    steady = [100 * 1.1 ** (i / 12) for i in range(37)]
    assert m.annual_log_return_vol(steady) == pytest.approx(0, abs=1e-12)
    jumpy = [100.0] * 12 + [200.0] * 12 + [200.0] * 13
    assert m.annual_log_return_vol(jumpy) == pytest.approx(math.log(2) / math.sqrt(3))


def test_combine_value_and_growth() -> None:
    value = Quantiles(90, 100, 110)
    same = combine_value_and_growth(value, Quantiles(1, 1, 1))
    assert (same.p10, same.p50, same.p90) == pytest.approx((90, 100, 110))
    combined = combine_value_and_growth(value, Quantiles(1.0, 1.2, 1.5))
    assert combined.p50 == pytest.approx(120)
    assert combined.p10 < combined.p50 < combined.p90
    # narrower than multiplying the tails together
    assert combined.p10 > 90 * 1.0 and combined.p90 < 110 * 1.5


def test_conformal_margin_and_widen() -> None:
    preds = [Quantiles(90, 100, 110)] * 4
    # log-space scores: two inside (negative), two outside by log(1.2) and log(1.5)
    actual = [100, 100, 132, 165]
    margin = conformal_log_margin(preds, actual, 0.8)  # k = ceil(5 * 0.8) = 4 -> largest
    assert margin == pytest.approx(math.log(1.5))
    wide = widen(Quantiles(90, 100, 110), margin)
    assert (wide.p10, wide.p50, wide.p90) == pytest.approx((60, 100, 165))
    assert conformal_log_margin(preds, [100] * 4, 0.8) < 0  # all inside -> narrows


def test_split_and_months() -> None:
    train, test = holdout_split(10, 0.2, seed=1)
    assert len(test) == 2 and sorted(train + test) == list(range(10))
    assert holdout_split(10, 0.2, seed=1) == (train, test)
    assert add_months(date(2026, 11, 1), 2) == date(2027, 1, 1)
    series = IndexSeries("X", (date(2026, 1, 1), date(2026, 2, 1)), (1.0, 2.0))
    assert series.level_at(date(2026, 2, 1)) == 2.0
    assert series.level_at(date(2026, 3, 1)) is None
