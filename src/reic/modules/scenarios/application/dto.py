from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reic.modules.scenarios.domain.risk import RiskInputs
from reic.modules.scenarios.domain.simulation import SimulationParams


class SimulateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_egp: float = Field(gt=0)
    horizon_years: int = Field(ge=1, le=40)
    annual_growth_mean: float = Field(gt=-0.5, lt=2)
    annual_growth_vol: float = Field(ge=0, le=1)
    gross_yield: float = Field(default=0.0, ge=0, le=0.5)
    upfront_cost_pct: float = Field(default=0.03, ge=0, lt=1)
    exit_cost_pct: float = Field(default=0.025, ge=0, lt=1)
    vacancy_mean: float = Field(default=0.10, ge=0, le=1)
    maintenance_pct: float = Field(default=0.10, ge=0, le=1)
    inflation_mean: float = Field(default=0.15, gt=-0.5, lt=2)
    inflation_vol: float = Field(default=0.05, ge=0, le=1)
    goal: Literal["live", "rent", "resell"] = "resell"
    years_to_delivery: int = Field(default=0, ge=0, le=40)
    n_paths: int = Field(default=5000, ge=100, le=50000)
    seed: int = 42

    @model_validator(mode="after")
    def _delivery_within_horizon(self) -> Self:
        if self.years_to_delivery > self.horizon_years:
            raise ValueError("years_to_delivery cannot exceed horizon_years")
        return self

    def to_params(self) -> SimulationParams:
        return SimulationParams(**self.model_dump())


class RiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    developer_on_time_rate: float = Field(ge=0, le=1)
    years_to_delivery: int = Field(ge=0, le=40)
    liquidity_tier: int = Field(ge=1, le=3)
    price_egp: float = Field(gt=0)
    value_p10: float = Field(ge=0)
    value_p50: float = Field(ge=0)
    prob_real_loss: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.value_p10 > self.value_p50:
            raise ValueError("value_p10 cannot exceed value_p50")
        return self

    def to_inputs(self) -> RiskInputs:
        return RiskInputs(**self.model_dump())
