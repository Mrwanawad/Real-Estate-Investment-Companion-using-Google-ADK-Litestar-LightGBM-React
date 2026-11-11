"""Inventory domain models. Pure: no framework or database imports."""

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

AreaType = Literal["urban", "coastal"]
UnitType = Literal["apartment", "duplex", "townhouse", "twin_house", "villa", "chalet"]
Finishing = Literal["core_shell", "semi", "fully"]
UnitStatus = Literal["available", "reserved", "sold"]
PaymentFrequency = Literal["monthly", "quarterly"]
DeveloperTier = Literal["A", "B", "C"]
Goal = Literal["live", "rent", "resell"]


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    name_en: str
    name_ar: str
    type: AreaType
    base_price_per_m2_2015: int
    liquidity_tier: int  # 1 = most liquid
    gross_rental_yield_base: float


@dataclass(frozen=True, slots=True)
class Developer:
    id: str
    name_en: str
    tier: DeveloperTier
    on_time_delivery_rate: float


@dataclass(frozen=True, slots=True)
class Project:
    id: str
    name_en: str
    name_ar: str
    area_id: str
    developer_id: str
    launch_year: int
    delivery_year: int
    amenities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaymentPlan:
    id: str
    project_id: str
    name: str
    down_payment_pct: float
    years: int
    frequency: PaymentFrequency
    delivery_payment_pct: float
    maintenance_pct: float
    cash_discount_pct: float


@dataclass(frozen=True, slots=True)
class Unit:
    code: str
    project_id: str
    type: UnitType
    bedrooms: int
    bua_m2: float
    garden_m2: float
    floor: int
    finishing: Finishing
    delivery_year: int
    status: UnitStatus
    price_egp: int
    view: str


@dataclass(frozen=True, slots=True)
class UnitDetail:
    """A unit together with the context needed to present and score it."""

    unit: Unit
    project: Project
    area: Area
    developer: Developer
    plans: tuple[PaymentPlan, ...]


class UnitQuery(BaseModel):
    """Search criteria. Amount fields are in EGP; every filter is optional."""

    model_config = ConfigDict(frozen=True)

    budget_max_egp: int | None = Field(default=None, gt=0)
    down_payment_available_egp: int | None = Field(default=None, ge=0)
    monthly_capacity_egp: int | None = Field(default=None, ge=0)
    area_ids: tuple[str, ...] = ()
    types: tuple[UnitType, ...] = ()
    bedrooms_min: int | None = Field(default=None, ge=0, le=10)
    delivery_by_year: int | None = Field(default=None, ge=2000, le=2100)
    status: UnitStatus | None = "available"

    @model_validator(mode="after")
    def _down_payment_within_budget(self) -> Self:
        if (
            self.budget_max_egp is not None
            and self.down_payment_available_egp is not None
            and self.down_payment_available_egp > self.budget_max_egp
        ):
            raise ValueError("down_payment_available_egp cannot exceed budget_max_egp")
        return self
