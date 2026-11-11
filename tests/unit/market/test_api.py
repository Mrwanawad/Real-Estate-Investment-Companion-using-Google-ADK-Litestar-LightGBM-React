from collections.abc import Iterator
from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from reic.bootstrap.market import build_market_router
from reic.modules.market.application.service import MarketService
from tests.unit.market.conftest import UNIT


@pytest.fixture
def client(market_service: MarketService) -> Iterator[TestClient[Any]]:
    app = Litestar(route_handlers=[build_market_router(market_service)])
    with TestClient(app=app) as test_client:
        yield test_client


def test_forecast_200(client: TestClient[Any]) -> None:
    response = client.get("/market/areas/NC/forecast", params={"horizon_months": 12})
    assert response.status_code == 200
    body = response.json()
    assert body["area_id"] == "NC" and len(body["forecast"]) == 12


def test_forecast_unknown_area_404(client: TestClient[Any]) -> None:
    assert client.get("/market/areas/XX/forecast").status_code == 404


def test_forecast_bad_horizon_400(client: TestClient[Any]) -> None:
    assert client.get("/market/areas/NC/forecast?horizon_months=0").status_code == 400
    assert client.get("/market/areas/NC/forecast?horizon_months=abc").status_code == 400


def test_unit_value_200(client: TestClient[Any]) -> None:
    response = client.post("/market/unit-value", json={"unit": UNIT, "horizon_years": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "lightgbm_quantile" and len(body["path"]) == 4


def test_unit_value_bad_input_400_and_unknown_area_404(client: TestClient[Any]) -> None:
    bad = client.post("/market/unit-value", json={"unit": {**UNIT, "type": "castle"}})
    assert bad.status_code == 400
    missing = client.post("/market/unit-value", json={"horizon_years": 3})
    assert missing.status_code == 400
    too_long = client.post("/market/unit-value", json={"unit": UNIT, "horizon_years": 50})
    assert too_long.status_code == 400
    unknown = client.post("/market/unit-value", json={"unit": {**UNIT, "area_id": "XX"}})
    assert unknown.status_code == 404


def test_rent_200_and_400(client: TestClient[Any]) -> None:
    ok = client.post("/market/rent", json={"unit": UNIT, "price_egp": 8_000_000})
    assert ok.status_code == 200
    assert ok.json()["gross_yield"] > 0
    bad = client.post("/market/rent", json={"unit": UNIT, "price_egp": -1})
    assert bad.status_code == 400
