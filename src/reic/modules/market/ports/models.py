"""Model ports. Implementations are synchronous and CPU-bound; the service runs them in a thread."""

from collections.abc import Sequence
from typing import Protocol

from reic.modules.market.domain.models import QuantilePath, Quantiles, RentFeatures, UnitFeatures


class Forecaster(Protocol):
    name: str

    def forecast(self, levels: Sequence[float], horizon: int) -> QuantilePath:
        """Monthly P10/P50/P90 for the `horizon` months after the last level."""
        ...


class UnitValueModel(Protocol):
    name: str

    def fit(self, features: Sequence[UnitFeatures], ppm2: Sequence[float]) -> None: ...

    def predict(self, features: Sequence[UnitFeatures]) -> list[Quantiles]:
        """Price per m2 quantiles, ordered p10 <= p50 <= p90."""
        ...


class RentModel(Protocol):
    name: str

    def fit(self, features: Sequence[RentFeatures], monthly_rent: Sequence[float]) -> None: ...

    def predict(self, features: Sequence[RentFeatures]) -> list[float]:
        """Median monthly rent in EGP."""
        ...
