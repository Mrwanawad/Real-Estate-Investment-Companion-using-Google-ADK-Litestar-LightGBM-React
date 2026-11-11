from collections.abc import Awaitable
from typing import Annotated, Any

from litestar import Controller, get, post
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import Parameter

from reic.modules.market.adapters.inbound.schemas import RentRequest, UnitValueRequest
from reic.modules.market.application.service import MAX_HORIZON_MONTHS, MarketService
from reic.modules.market.domain.errors import MarketError, UnknownAreaError


class MarketController(Controller):
    """`market_service` is injected by bootstrap. Unknown area -> 404, invalid input -> 400."""

    path = "/market"

    @get("/areas/{area_id:str}/forecast")
    async def forecast(
        self,
        area_id: str,
        market_service: MarketService,
        horizon_months: Annotated[int, Parameter(ge=1, le=MAX_HORIZON_MONTHS)] = 60,
    ) -> dict[str, Any]:
        return await _call(market_service.forecast_area(area_id, horizon_months))

    @post("/unit-value", status_code=200)
    async def unit_value(
        self, data: UnitValueRequest, market_service: MarketService
    ) -> dict[str, Any]:
        return await _call(market_service.unit_value(data.unit.model_dump(), data.horizon_years))

    @post("/rent", status_code=200)
    async def rent(self, data: RentRequest, market_service: MarketService) -> dict[str, Any]:
        return await _call(market_service.rent_estimate(data.unit.model_dump(), data.price_egp))


async def _call(coro: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    try:
        return await coro
    except UnknownAreaError as exc:
        raise NotFoundException(str(exc)) from exc
    except MarketError as exc:
        raise ValidationException(str(exc)) from exc
