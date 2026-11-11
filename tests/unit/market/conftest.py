import pytest

from reic.bootstrap.market import build_csv_market_service
from reic.modules.market.application.service import MarketService

UNIT = {
    "area_id": "NC",
    "type": "apartment",
    "bedrooms": 3,
    "bua_m2": 160,
    "garden_m2": 0,
    "floor": 2,
    "finishing": "semi",
    "delivery_year": 2027,
    "developer_tier": "A",
}


@pytest.fixture(scope="session")
def market_service() -> MarketService:
    """One CSV-backed service per test session, so models train once."""
    return build_csv_market_service()
