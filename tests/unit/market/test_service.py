from collections.abc import Sequence

import pytest

from reic.bootstrap.market import SYNTHETIC_DIR
from reic.modules.market.adapters.outbound.csv_source import CsvMarketDataSource
from reic.modules.market.adapters.outbound.forecasters import (
    ArimaForecaster,
    SeasonalNaiveForecaster,
)
from reic.modules.market.adapters.outbound.lightgbm_models import LightGbmRentModel
from reic.modules.market.application.backtest import rolling_origin_backtest
from reic.modules.market.application.service import BASELINE_NOTE, MarketService
from reic.modules.market.domain.errors import InvalidInputError, UnknownAreaError
from reic.modules.market.domain.models import Quantiles, UnitFeatures
from tests.unit.market.conftest import UNIT


def _ordered(q: dict[str, float]) -> bool:
    return q["p10"] <= q["p50"] <= q["p90"]


async def test_forecast_shape_and_monotone_quantiles(market_service: MarketService) -> None:
    out = await market_service.forecast_area("NC", horizon_months=24)
    assert out["model"] == "arima_110_drift_log"
    assert out["last_month"] == "2026-10-01"
    assert len(out["history"]) == 36 and out["history"][-1]["month"] == "2026-10-01"
    assert len(out["forecast"]) == 24
    assert out["forecast"][0]["month"] == "2026-11-01"
    assert out["forecast"][-1]["month"] == "2028-10-01"
    assert all(_ordered(p) for p in out["forecast"])
    widths = [p["p90"] - p["p10"] for p in out["forecast"]]
    assert widths == sorted(widths)  # uncertainty grows with horizon
    assert _ordered(out["annual_growth"])
    bt = out["backtest"]
    assert bt["points"] == 36 and 0 < bt["mape"] < 0.2 and 0 <= bt["coverage_80"] <= 1


async def test_unknown_area_and_bad_horizon(market_service: MarketService) -> None:
    with pytest.raises(UnknownAreaError):
        await market_service.forecast_area("XX")
    with pytest.raises(InvalidInputError):
        await market_service.forecast_area("NC", horizon_months=0)


async def test_unit_value_quantiles_ordered(market_service: MarketService) -> None:
    out = await market_service.unit_value({**UNIT, "price_egp": 9_000_000}, horizon_years=5)
    assert out["model"] == "lightgbm_quantile"
    assert "note" not in out
    assert out["holdout"]["mae_model"] < out["holdout"]["mae_baseline"]
    assert _ordered(out["current"]) and _ordered(out["at_horizon"])
    assert [p["year"] for p in out["path"]] == [0, 1, 2, 3, 4, 5]
    assert all(_ordered(p) for p in out["path"])
    assert out["path"][0]["p50"] == out["current"]["p50"]
    assert out["at_horizon"]["p50"] > out["current"]["p50"]  # nominal index drifts up
    assert out["price_vs_p50"] is not None


async def test_unit_value_rejects_bad_unit(market_service: MarketService) -> None:
    with pytest.raises(InvalidInputError):
        await market_service.unit_value({**UNIT, "bua_m2": -5}, horizon_years=5)
    with pytest.raises(InvalidInputError):
        await market_service.unit_value(UNIT, horizon_years=0)
    with pytest.raises(UnknownAreaError):
        await market_service.unit_value({**UNIT, "area_id": "XX"}, horizon_years=3)


async def test_rent_and_volatility(market_service: MarketService) -> None:
    out = await market_service.rent_estimate(UNIT, price_egp=10_000_000)
    assert out["model"] == "lightgbm" and out["monthly_rent_p50"] > 0
    assert out["gross_yield"] == pytest.approx(12 * out["monthly_rent_p50"] / 1e7, rel=0.01)
    assert 0 < out["holdout"]["mape"] < 0.5
    assert (await market_service.rent_estimate(UNIT, None))["gross_yield"] is None
    vol = await market_service.annual_volatility("NC")
    assert 0 < vol < 1


class _ConstantModel:
    """A deliberately useless candidate: predicts the same price per m2 for every unit."""

    name = "constant"

    def fit(self, features: Sequence[UnitFeatures], ppm2: Sequence[float]) -> None:
        pass

    def predict(self, features: Sequence[UnitFeatures]) -> list[Quantiles]:
        return [Quantiles(1.0, 1.0, 1.0) for _ in features]


async def test_gate_falls_back_to_baseline() -> None:
    service = MarketService(
        CsvMarketDataSource(SYNTHETIC_DIR),
        SeasonalNaiveForecaster(),
        unit_model_factory=_ConstantModel,
        rent_model_factory=LightGbmRentModel,
    )
    out = await service.unit_value(UNIT, horizon_years=2)
    assert out["model"] == "baseline"
    assert out["note"] == BASELINE_NOTE
    assert out["holdout"]["mae_model"] > out["holdout"]["mae_baseline"]
    assert _ordered(out["current"])


def test_arima_beats_seasonal_naive_on_backtest() -> None:
    levels = CsvMarketDataSource(SYNTHETIC_DIR).load_sync().index["SZ"].levels
    arima = rolling_origin_backtest(ArimaForecaster(), levels)
    naive = rolling_origin_backtest(SeasonalNaiveForecaster(), levels)
    assert arima.mase < naive.mase
