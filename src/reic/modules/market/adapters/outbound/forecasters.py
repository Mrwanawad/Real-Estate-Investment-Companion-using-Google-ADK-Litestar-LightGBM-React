"""Area index forecasters. Both model the log index, so intervals stay positive and skewed."""

import math
import statistics
import warnings
from collections.abc import Sequence

import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

from reic.modules.market.domain.models import QuantilePath

Z90 = 1.2815515655446004  # standard normal 0.9 quantile


def _path(log_mean: Sequence[float], log_sd: Sequence[float]) -> QuantilePath:
    return QuantilePath(
        p10=tuple(math.exp(m - Z90 * s) for m, s in zip(log_mean, log_sd, strict=True)),
        p50=tuple(math.exp(m) for m in log_mean),
        p90=tuple(math.exp(m + Z90 * s) for m, s in zip(log_mean, log_sd, strict=True)),
    )


class SeasonalNaiveForecaster:
    """Baseline: same month last year. Spread from in-sample seasonal differences, widening
    with the square root of the number of seasons ahead."""

    name = "seasonal_naive"

    def __init__(self, season: int = 12) -> None:
        self._season = season

    def forecast(self, levels: Sequence[float], horizon: int) -> QuantilePath:
        m = self._season
        logs = [math.log(x) for x in levels]
        sd = statistics.stdev(logs[i] - logs[i - m] for i in range(m, len(logs)))
        mean = [logs[len(logs) - m + (h % m)] for h in range(horizon)]
        spread = [sd * math.sqrt(h // m + 1) for h in range(horizon)]
        return _path(mean, spread)


class ArimaForecaster:
    """Default: ARIMA(1,1,0) with drift on the log index (statsmodels SARIMAX).

    Picked on the rolling-origin backtest over the synthetic indices: seasonal terms and an MA
    term added fit time without lowering MAPE. Intervals are the Gaussian prediction intervals
    of the log model, exponentiated.
    """

    name = "arima_110_drift_log"

    def __init__(self, order: tuple[int, int, int] = (1, 1, 0)) -> None:
        self._order = order

    def forecast(self, levels: Sequence[float], horizon: int) -> QuantilePath:
        y = np.log(np.asarray(levels, dtype=float))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = SARIMAX(y, order=self._order, trend="c").fit(disp=False)
            pred = fitted.get_forecast(horizon)
        mean = np.asarray(pred.predicted_mean, dtype=float)
        sd = np.sqrt(np.asarray(pred.var_pred_mean, dtype=float))
        return _path(mean.tolist(), sd.tolist())
