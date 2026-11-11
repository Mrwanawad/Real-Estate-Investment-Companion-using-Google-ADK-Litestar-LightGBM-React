"""MarketService: area forecasts, unit value and rent, trained lazily and cached in memory.

All model work is CPU-bound and runs in a worker thread. One asyncio lock guards every lazy
fit, so concurrent first requests train once.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from reic.modules.market.application.backtest import rolling_origin_backtest
from reic.modules.market.domain import metrics as m
from reic.modules.market.domain.errors import InvalidInputError, UnknownAreaError
from reic.modules.market.domain.models import (
    BacktestResult,
    IndexSeries,
    MarketData,
    QuantilePath,
    Quantiles,
    RentFeatures,
    UnitFeatures,
)
from reic.modules.market.domain.valuation import (
    AreaMedianBaseline,
    add_months,
    combine_value_and_growth,
    conformal_log_margin,
    holdout_split,
    widen,
)
from reic.modules.market.ports.data_source import MarketDataSource
from reic.modules.market.ports.models import Forecaster, RentModel, UnitValueModel

MAX_HORIZON_MONTHS = 120
MAX_HORIZON_YEARS = MAX_HORIZON_MONTHS // 12
HISTORY_MONTHS = 36
CONFORMAL_COVERAGE = 0.8  # target share of prices inside the served P10-P90
BASELINE_NOTE = (
    "The LightGBM model did not beat the area-median price per m2 baseline on holdout MAE, "
    "so the baseline is used."
)


@dataclass(frozen=True, slots=True)
class _AreaFit:
    series: IndexSeries
    path: QuantilePath  # MAX_HORIZON_MONTHS long
    backtest: BacktestResult

    def growth(self, months: int) -> Quantiles:
        """Index growth ratio quantiles `months` after the last observation (0 -> 1, 1, 1)."""
        if months == 0:
            return Quantiles(1.0, 1.0, 1.0)
        return self.path.at(months - 1).scaled(1 / self.series.levels[-1])


@dataclass(frozen=True, slots=True)
class _ValueFit:
    model: UnitValueModel
    mae_model: float
    mae_baseline: float
    promoted: bool
    coverage_80_model: float  # holdout share of actual price/m2 inside the candidate's P10-P90


@dataclass(frozen=True, slots=True)
class _RentFit:
    model: RentModel
    mae: float
    mape: float
    train_rows: int


class MarketService:
    def __init__(
        self,
        source: MarketDataSource,
        forecaster: Forecaster,
        unit_model_factory: Callable[[], UnitValueModel],
        rent_model_factory: Callable[[], RentModel],
        *,
        holdout_fraction: float = 0.2,
        seed: int = 7,
    ) -> None:
        self._source = source
        self._forecaster = forecaster
        self._unit_model_factory = unit_model_factory
        self._rent_model_factory = rent_model_factory
        self._holdout_fraction = holdout_fraction
        self._seed = seed
        self._lock = asyncio.Lock()
        self._data: MarketData | None = None
        self._areas: dict[str, _AreaFit] = {}
        self._value: _ValueFit | None = None
        self._rent: _RentFit | None = None

    # ---- public facade -------------------------------------------------------------------

    async def forecast_area(self, area_id: str, horizon_months: int = 60) -> dict[str, Any]:
        if not 1 <= horizon_months <= MAX_HORIZON_MONTHS:
            raise InvalidInputError(f"horizon_months must be between 1 and {MAX_HORIZON_MONTHS}")
        fit = await self._area_fit(area_id)
        series, last = fit.series, fit.series.months[-1]
        history = zip(series.months[-HISTORY_MONTHS:], series.levels[-HISTORY_MONTHS:], strict=True)
        return {
            "area_id": area_id,
            "model": self._forecaster.name,
            "last_month": last.isoformat(),
            "history": [{"month": d.isoformat(), "index": round(v, 2)} for d, v in history],
            "forecast": [
                {"month": add_months(last, i + 1).isoformat(), **fit.path.at(i).as_dict(2)}
                for i in range(horizon_months)
            ],
            "annual_growth": _annualise(fit.growth(horizon_months), horizon_months),
            "backtest": fit.backtest.as_dict(),
        }

    async def unit_value(self, unit: Mapping[str, Any], horizon_years: int) -> dict[str, Any]:
        if not 1 <= horizon_years <= MAX_HORIZON_YEARS:
            raise InvalidInputError(f"horizon_years must be between 1 and {MAX_HORIZON_YEARS}")
        features = _parse(UnitFeatures, unit)
        area = await self._area_fit(features.area_id)
        value = await self._value_fit()
        ppm2 = (await asyncio.to_thread(value.model.predict, [features]))[0]
        current = ppm2.scaled(features.bua_m2)
        path = [
            {"year": y, **combine_value_and_growth(current, area.growth(12 * y)).as_dict()}
            for y in range(horizon_years + 1)
        ]
        at_horizon = {k: v for k, v in path[-1].items() if k != "year"}
        result: dict[str, Any] = {
            "current": current.as_dict(),
            "at_horizon": at_horizon,
            "path": path,
            "model": value.model.name,
            "holdout": {
                "mae_model": round(value.mae_model),
                "mae_baseline": round(value.mae_baseline),
                "unit": "EGP per m2",
            },
            "annual_growth": _annualise(area.growth(12 * horizon_years), 12 * horizon_years),
            "price_vs_p50": (
                round(features.price_egp / current.p50 - 1, 4) if features.price_egp else None
            ),
        }
        if not value.promoted:
            result["note"] = BASELINE_NOTE
        return result

    async def rent_estimate(
        self, unit: Mapping[str, Any], price_egp: float | None = None
    ) -> dict[str, Any]:
        if price_egp is not None and price_egp <= 0:
            raise InvalidInputError("price_egp must be positive")
        features = _parse(RentFeatures, unit)
        await self._area_fit(features.area_id)  # validates the area
        rent = await self._rent_fit()
        monthly = (await asyncio.to_thread(rent.model.predict, [features]))[0]
        return {
            "monthly_rent_p50": round(monthly, -2),
            "gross_yield": round(12 * monthly / price_egp, 4) if price_egp else None,
            "model": rent.model.name,
            "holdout": {"mae": round(rent.mae), "mape": round(rent.mape, 4)},
        }

    async def annual_volatility(self, area_id: str) -> float:
        series = (await self._area_fit(area_id)).series
        return round(m.annual_log_return_vol(series.levels), 4)

    async def area_ids(self) -> list[str]:
        return sorted((await self._load()).index)

    async def evaluation(self) -> dict[str, Any]:
        """Backtest of every area plus both holdouts. Used by the training script."""
        areas = {a: (await self._area_fit(a)).backtest for a in await self.area_ids()}
        value, rent = await self._value_fit(), await self._rent_fit()
        keys = ("mape", "mase", "coverage_80", "pinball")
        mean = {k: sum(getattr(b, k) for b in areas.values()) / len(areas) for k in keys}
        return {
            "forecast": {
                "model": self._forecaster.name,
                "mean_over_areas": {k: round(v, 4) for k, v in mean.items()},
                "per_area": {a: b.as_dict() for a, b in areas.items()},
            },
            "unit_value": {
                "candidate": self._unit_model_factory().name,
                "served": value.model.name,
                "promoted": value.promoted,
                "holdout_mae_model": round(value.mae_model),
                "holdout_mae_baseline": round(value.mae_baseline),
                "holdout_coverage_80_model": round(value.coverage_80_model, 3),
                "calibration": f"split conformal (CQR, log space), target {CONFORMAL_COVERAGE}",
                "served_log_margin": (
                    round(value.model.log_margin, 4)
                    if isinstance(value.model, _Conformal)
                    else None
                ),
                "unit": "EGP per m2",
            },
            "rent": {
                "model": rent.model.name,
                "holdout_mae": round(rent.mae),
                "holdout_mape": round(rent.mape, 4),
                "train_rows": rent.train_rows,
            },
        }

    # ---- lazy training -------------------------------------------------------------------

    async def _load(self) -> MarketData:
        if self._data is None:
            async with self._lock:
                if self._data is None:
                    self._data = await self._source.load()
        return self._data

    async def _area_fit(self, area_id: str) -> _AreaFit:
        if area_id in self._areas:
            return self._areas[area_id]
        data = await self._load()
        series = data.index.get(area_id)
        if series is None:
            raise UnknownAreaError(area_id)
        async with self._lock:
            if area_id not in self._areas:
                self._areas[area_id] = await asyncio.to_thread(self._fit_area, series)
        return self._areas[area_id]

    def _fit_area(self, series: IndexSeries) -> _AreaFit:
        return _AreaFit(
            series=series,
            path=self._forecaster.forecast(series.levels, MAX_HORIZON_MONTHS),
            backtest=rolling_origin_backtest(self._forecaster, series.levels),
        )

    async def _value_fit(self) -> _ValueFit:
        if self._value is None:
            data = await self._load()
            async with self._lock:
                if self._value is None:
                    self._value = await asyncio.to_thread(self._fit_value, data)
        return self._value

    def _fit_value(self, data: MarketData) -> _ValueFit:
        """Promotion gate: the candidate must beat the area-median baseline on holdout MAE of
        price per m2 (its P50).

        The candidate's P10/P90 are split-conformal calibrated: holdout evaluation fits on 60%,
        calibrates on 20% and scores on the untouched 20% test set. The served candidate fits
        on 80% and calibrates on the remaining 20%. The baseline uses empirical quantiles and
        is refitted on all units when served.
        """
        features = [s.features for s in data.unit_sales]
        ppm2 = [s.price_per_m2 for s in data.unit_sales]
        rest, test = holdout_split(len(features), self._holdout_fraction, self._seed)
        actual = [ppm2[i] for i in test]

        def calibrated(rows: list[int]) -> UnitValueModel:
            fit_part, cal_part = holdout_split(len(rows), 0.25, self._seed + 1)
            fit_rows, cal_rows = [rows[i] for i in fit_part], [rows[i] for i in cal_part]
            model = self._unit_model_factory()
            model.fit([features[i] for i in fit_rows], [ppm2[i] for i in fit_rows])
            margin = conformal_log_margin(
                model.predict([features[i] for i in cal_rows]),
                [ppm2[i] for i in cal_rows],
                CONFORMAL_COVERAGE,
            )
            return _Conformal(model, margin)

        candidate = calibrated(rest)
        pred = candidate.predict([features[i] for i in test])
        mae_model = m.mae(actual, [q.p50 for q in pred])
        coverage_model = m.coverage(actual, [q.p10 for q in pred], [q.p90 for q in pred])

        baseline = AreaMedianBaseline()
        baseline.fit([features[i] for i in rest], [ppm2[i] for i in rest])
        mae_baseline = m.mae(actual, [q.p50 for q in baseline.predict([features[i] for i in test])])

        promoted = mae_model < mae_baseline
        if promoted:
            served: UnitValueModel = calibrated(list(range(len(features))))
        else:
            served = AreaMedianBaseline()
            served.fit(features, ppm2)
        return _ValueFit(served, mae_model, mae_baseline, promoted, coverage_model)

    async def _rent_fit(self) -> _RentFit:
        if self._rent is None:
            data = await self._load()
            async with self._lock:
                if self._rent is None:
                    self._rent = await asyncio.to_thread(self._fit_rent, data)
        return self._rent

    def _fit_rent(self, data: MarketData) -> _RentFit:
        """Listings span 2019-2026 in nominal EGP. Each rent is restated in money of the latest
        index month (rent x index_last / index_at_listing) so the model prices rent today."""
        features: list[RentFeatures] = []
        rents: list[float] = []
        for listing in data.rentals:
            series = data.index.get(listing.features.area_id)
            if series is None:
                continue
            level = series.level_at(listing.listing_date.replace(day=1))
            if level is None:
                continue
            features.append(listing.features)
            rents.append(listing.monthly_rent_egp * series.levels[-1] / level)
        train, test = holdout_split(len(features), self._holdout_fraction, self._seed)
        model = self._rent_model_factory()
        model.fit([features[i] for i in train], [rents[i] for i in train])
        actual = [rents[i] for i in test]
        pred = model.predict([features[i] for i in test])
        mae, mape = m.mae(actual, pred), m.mape(actual, pred)
        served = self._rent_model_factory()
        served.fit(features, rents)
        return _RentFit(served, mae, mape, len(features))


class _Conformal:
    """Wraps a fitted quantile model and widens its P10/P90 by a calibrated log margin."""

    def __init__(self, inner: UnitValueModel, log_margin: float) -> None:
        self.name = inner.name
        self._inner = inner
        self.log_margin = log_margin

    def fit(self, features: Sequence[UnitFeatures], ppm2: Sequence[float]) -> None:
        raise RuntimeError("conformal wrapper is built from an already fitted model")

    def predict(self, features: Sequence[UnitFeatures]) -> list[Quantiles]:
        return [widen(q, self.log_margin) for q in self._inner.predict(features)]


def _annualise(growth: Quantiles, months: int) -> dict[str, float]:
    return Quantiles(
        m.annualised(growth.p10, months),
        m.annualised(growth.p50, months),
        m.annualised(growth.p90, months),
    ).as_dict(4)


def _parse[T: RentFeatures](model: type[T], unit: Mapping[str, Any]) -> T:
    if isinstance(unit, model):
        return unit
    try:
        return model.model_validate(dict(unit))
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidInputError(f"invalid unit: {exc}") from exc
