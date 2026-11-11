"""Market domain types. Synthetic demo data feeds these; nothing here is a real price."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UnitType = Literal["apartment", "villa", "chalet", "townhouse", "duplex", "twin_house"]
Finishing = Literal["core_shell", "semi", "fully"]
DeveloperTier = Literal["A", "B", "C"]


class RentFeatures(BaseModel):
    """Features the rent model needs. Extra keys (code, view, ...) are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    area_id: str = Field(min_length=1, max_length=8)
    type: UnitType
    bedrooms: int = Field(ge=0, le=10)
    bua_m2: float = Field(gt=0, le=5000)
    finishing: Finishing
    furnished: bool = False


class UnitFeatures(RentFeatures):
    """Features the unit value model needs, plus an optional asking price."""

    garden_m2: float = Field(default=0, ge=0, le=10000)
    floor: int = Field(default=0, ge=0, le=60)
    delivery_year: int = Field(ge=2000, le=2045)
    developer_tier: DeveloperTier = "B"
    price_egp: float | None = Field(default=None, gt=0)


@dataclass(frozen=True, slots=True)
class Quantiles:
    p10: float
    p50: float
    p90: float

    def ordered(self) -> "Quantiles":
        lo, mid, hi = sorted((self.p10, self.p50, self.p90))
        return Quantiles(lo, mid, hi)

    def scaled(self, factor: float) -> "Quantiles":
        return Quantiles(self.p10 * factor, self.p50 * factor, self.p90 * factor)

    def as_dict(self, digits: int | None = None) -> dict[str, float]:
        def r(x: float) -> float:
            return float(round(x)) if digits is None else round(x, digits)

        return {"p10": r(self.p10), "p50": r(self.p50), "p90": r(self.p90)}


@dataclass(frozen=True, slots=True)
class QuantilePath:
    """Monthly quantile forecast; element i is month i+1 after the last observation."""

    p10: tuple[float, ...]
    p50: tuple[float, ...]
    p90: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.p50)

    def at(self, i: int) -> Quantiles:
        return Quantiles(self.p10[i], self.p50[i], self.p90[i])


@dataclass(frozen=True, slots=True)
class IndexSeries:
    """Monthly nominal price index of one area, oldest first, months on the 1st."""

    area_id: str
    months: tuple[date, ...]
    levels: tuple[float, ...]

    def level_at(self, month: date) -> float | None:
        lo, hi = 0, len(self.months)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.months[mid] < month:
                lo = mid + 1
            else:
                hi = mid
        if lo < len(self.months) and self.months[lo] == month:
            return self.levels[lo]
        return None


@dataclass(frozen=True, slots=True)
class UnitSale:
    features: UnitFeatures
    price_egp: float

    @property
    def price_per_m2(self) -> float:
        return self.price_egp / self.features.bua_m2


@dataclass(frozen=True, slots=True)
class RentalListing:
    listing_date: date
    features: RentFeatures
    monthly_rent_egp: float


@dataclass(frozen=True, slots=True)
class MarketData:
    index: dict[str, IndexSeries]
    unit_sales: tuple[UnitSale, ...]
    rentals: tuple[RentalListing, ...]


@dataclass(frozen=True, slots=True)
class BacktestResult:
    mape: float
    mase: float
    coverage_80: float
    pinball: float
    origins: int
    horizon: int
    points: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mape": round(self.mape, 4),
            "mase": round(self.mase, 3),
            "coverage_80": round(self.coverage_80, 3),
            "pinball": round(self.pinball, 3),
            "origins": self.origins,
            "horizon": self.horizon,
            "points": self.points,
        }
