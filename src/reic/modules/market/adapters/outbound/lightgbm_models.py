"""LightGBM unit value (quantile) and rent models. Both learn on log targets."""

from collections.abc import Sequence
from typing import Any, get_args

import lightgbm as lgb
import numpy as np
import pandas as pd

from reic.modules.market.domain.models import (
    DeveloperTier,
    Finishing,
    Quantiles,
    RentFeatures,
    UnitFeatures,
    UnitType,
)

_FIXED_CATEGORIES = {
    "type": list(get_args(UnitType)),
    "finishing": list(get_args(Finishing)),
    "developer_tier": list(get_args(DeveloperTier)),
}
_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 10,
    "subsample": 0.9,
    "subsample_freq": 1,
    "colsample_bytree": 0.9,
    "n_jobs": 2,
    "verbose": -1,
}


class _Frame:
    """Builds feature frames with stable categorical codes between fit and predict."""

    def __init__(self, columns: Sequence[str], categorical: Sequence[str]) -> None:
        self._columns = list(columns)
        self._categorical = list(categorical)
        self._categories: dict[str, list[str]] = {}

    def fit(self, rows: Sequence[RentFeatures]) -> pd.DataFrame:
        self._categories = {
            c: _FIXED_CATEGORIES.get(c) or sorted({str(getattr(r, c)) for r in rows})
            for c in self._categorical
        }
        return self.transform(rows)

    def transform(self, rows: Sequence[RentFeatures]) -> pd.DataFrame:
        df = pd.DataFrame([{c: getattr(r, c) for c in self._columns} for r in rows])
        for c in self._categorical:
            df[c] = pd.Categorical(df[c].astype(str), categories=self._categories[c])
        for c in set(self._columns) - set(self._categorical):
            df[c] = df[c].astype(float)
        return df


class LightGbmQuantileValueModel:
    """Three quantile regressors (0.1, 0.5, 0.9) on log price per m2."""

    name = "lightgbm_quantile"
    QUANTILES = (0.1, 0.5, 0.9)

    def __init__(self, seed: int = 7) -> None:
        self._seed = seed
        self._frame = _Frame(
            [
                "area_id",
                "type",
                "bedrooms",
                "bua_m2",
                "garden_m2",
                "floor",
                "finishing",
                "delivery_year",
                "developer_tier",
            ],
            ["area_id", "type", "finishing", "developer_tier"],
        )
        self._models: list[lgb.LGBMRegressor] = []

    def fit(self, features: Sequence[UnitFeatures], ppm2: Sequence[float]) -> None:
        x = self._frame.fit(features)
        y = np.log(np.asarray(ppm2, dtype=float))
        self._models = [
            lgb.LGBMRegressor(
                objective="quantile", alpha=q, random_state=self._seed, **_PARAMS
            ).fit(x, y)
            for q in self.QUANTILES
        ]

    def predict(self, features: Sequence[UnitFeatures]) -> list[Quantiles]:
        if not self._models:
            raise RuntimeError("model is not fitted")
        x = self._frame.transform(features)
        preds = np.sort(np.exp(np.column_stack([m.predict(x) for m in self._models])), axis=1)
        return [Quantiles(float(a), float(b), float(c)) for a, b, c in preds]


class LightGbmRentModel:
    """L2 regression on log monthly rent; exp of the prediction is a median-type estimate."""

    name = "lightgbm"

    def __init__(self, seed: int = 7) -> None:
        self._seed = seed
        self._frame = _Frame(
            ["area_id", "type", "bedrooms", "bua_m2", "finishing", "furnished"],
            ["area_id", "type", "finishing"],
        )
        self._model: lgb.LGBMRegressor | None = None

    def fit(self, features: Sequence[RentFeatures], monthly_rent: Sequence[float]) -> None:
        x = self._frame.fit(features)
        y = np.log(np.asarray(monthly_rent, dtype=float))
        self._model = lgb.LGBMRegressor(random_state=self._seed, **_PARAMS).fit(x, y)

    def predict(self, features: Sequence[RentFeatures]) -> list[float]:
        if self._model is None:
            raise RuntimeError("model is not fitted")
        x = self._frame.transform(features)
        return [float(v) for v in np.exp(self._model.predict(x))]
