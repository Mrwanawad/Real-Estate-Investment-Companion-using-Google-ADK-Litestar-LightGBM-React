from pydantic import BaseModel, ConfigDict, Field

from reic.modules.market.application.service import MAX_HORIZON_YEARS
from reic.modules.market.domain.models import RentFeatures, UnitFeatures


class UnitValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: UnitFeatures
    horizon_years: int = Field(default=5, ge=1, le=MAX_HORIZON_YEARS)


class RentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: RentFeatures
    price_egp: float | None = Field(default=None, gt=0)
