"""Wiring for the market module: service construction (SQL or CSV source) and the router."""

from pathlib import Path

from litestar import Router
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.market.adapters.inbound.controller import MarketController
from reic.modules.market.adapters.outbound.csv_source import CsvMarketDataSource
from reic.modules.market.adapters.outbound.forecasters import ArimaForecaster
from reic.modules.market.adapters.outbound.lightgbm_models import (
    LightGbmQuantileValueModel,
    LightGbmRentModel,
)
from reic.modules.market.adapters.outbound.sql_source import SqlMarketDataSource
from reic.modules.market.application.service import MarketService
from reic.modules.market.ports.data_source import MarketDataSource

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "demo_data" / "synthetic"


def _service(source: MarketDataSource) -> MarketService:
    return MarketService(
        source,
        ArimaForecaster(),
        unit_model_factory=LightGbmQuantileValueModel,
        rent_model_factory=LightGbmRentModel,
    )


def build_market_service(session_factory: async_sessionmaker[AsyncSession]) -> MarketService:
    """Trains lazily from Postgres on first use; models stay cached for the process lifetime."""
    return _service(SqlMarketDataSource(session_factory))


def build_csv_market_service(directory: Path = SYNTHETIC_DIR) -> MarketService:
    """Same service over the synthetic CSVs (tests, scripts, no database)."""
    return _service(CsvMarketDataSource(directory))


def build_market_router(service: MarketService) -> Router:
    def provide_service() -> MarketService:
        return service

    return Router(
        path="/",
        route_handlers=[MarketController],
        dependencies={"market_service": Provide(provide_service, sync_to_thread=False)},
    )
