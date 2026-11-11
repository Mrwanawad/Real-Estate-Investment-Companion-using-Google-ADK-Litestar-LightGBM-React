from collections.abc import Sequence

from reic.modules.market.domain import metrics as m
from reic.modules.market.domain.models import BacktestResult
from reic.modules.market.ports.models import Forecaster


def rolling_origin_backtest(
    forecaster: Forecaster,
    levels: Sequence[float],
    *,
    origins: int = 3,
    horizon: int = 12,
    season: int = 12,
) -> BacktestResult:
    """Refit at `origins` consecutive, non-overlapping cut-offs ending at the last observation.

    With the defaults the cut-offs are n-36, n-24 and n-12 and each forecasts the next 12 months.
    MAPE, 80% coverage and pinball (index points, mean over q=0.1/0.5/0.9) pool all forecast
    points; MASE is averaged over origins, each scaled by its own in-sample seasonal naive MAE.
    """
    if len(levels) < origins * horizon + 2 * season:
        raise ValueError("series too short for the requested backtest")
    actual_all: list[float] = []
    p10_all: list[float] = []
    p50_all: list[float] = []
    p90_all: list[float] = []
    mases: list[float] = []
    for k in range(origins, 0, -1):
        cut = len(levels) - k * horizon
        train, actual = list(levels[:cut]), list(levels[cut : cut + horizon])
        path = forecaster.forecast(train, horizon)
        mases.append(m.mase(actual, path.p50, train, season))
        actual_all += actual
        p10_all += path.p10
        p50_all += path.p50
        p90_all += path.p90
    return BacktestResult(
        mape=m.mape(actual_all, p50_all),
        mase=sum(mases) / len(mases),
        coverage_80=m.coverage(actual_all, p10_all, p90_all),
        pinball=m.mean_pinball(actual_all, {0.1: p10_all, 0.5: p50_all, 0.9: p90_all}),
        origins=origins,
        horizon=horizon,
        points=len(actual_all),
    )
