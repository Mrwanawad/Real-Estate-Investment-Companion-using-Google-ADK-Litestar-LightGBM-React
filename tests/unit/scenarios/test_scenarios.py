from collections.abc import Iterator
from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from reic.bootstrap.scenarios import build_scenarios_router
from reic.modules.scenarios.application.service import ScenarioService
from reic.modules.scenarios.domain.errors import ScenarioValidationError

BASE: dict[str, Any] = {
    "price_egp": 5_000_000,
    "horizon_years": 5,
    "annual_growth_mean": 0.12,
    "annual_growth_vol": 0.10,
    "gross_yield": 0.07,
    "years_to_delivery": 2,
}
service = ScenarioService()


def test_deterministic_with_seed() -> None:
    assert service.simulate(BASE) == service.simulate(BASE)
    assert service.simulate({**BASE, "seed": 1}) != service.simulate({**BASE, "seed": 2})


def test_quantile_ordering() -> None:
    out = service.simulate(BASE)
    for key in ("value_at_horizon", "net_rent_total", "total_return_pct", "irr"):
        assert out[key]["p10"] <= out[key]["p50"] <= out[key]["p90"]
    assert len(out["value_path"]) == BASE["horizon_years"] + 1
    assert {s["driver"] for s in out["sensitivity"]} == {
        "annual_growth",
        "gross_yield",
        "vacancy",
        "exit_cost",
    }
    assert out["assumptions"]["price_egp"] == BASE["price_egp"]


def test_zero_vol_matches_closed_form() -> None:
    data = {
        **BASE,
        "annual_growth_vol": 0,
        "inflation_vol": 0,
        "vacancy_mean": 0,
        "years_to_delivery": 0,
        "n_paths": 100,
    }
    out = service.simulate(data)
    price, g, y, infl = 5_000_000, 0.12, 0.07, 0.15
    value = price * (1 + g) ** 5
    rent = [price * y * (1 + infl) ** (t - 1) * 0.9 for t in range(1, 6)]
    cost = price * 1.03
    expected = (value * 0.975 + sum(rent)) / cost - 1
    assert out["value_at_horizon"]["p50"] == pytest.approx(value)
    assert out["value_at_horizon"]["p10"] == pytest.approx(value)
    assert out["net_rent_total"]["p50"] == pytest.approx(sum(rent))
    assert out["total_return_pct"]["p50"] == pytest.approx(expected * 100)
    assert out["prob_loss"] == 0.0
    irr = out["irr"]["p50"]
    npv = -cost + sum(r / (1 + irr) ** t for t, r in enumerate(rent, start=1))
    npv += value * 0.975 / (1 + irr) ** 5
    assert abs(npv) < 1.0


def test_no_rent_before_delivery() -> None:
    out = service.simulate({**BASE, "years_to_delivery": 5})
    assert out["net_rent_total"]["p90"] == 0


def test_break_even_sanity() -> None:
    good = service.simulate({**BASE, "annual_growth_mean": 0.25, "annual_growth_vol": 0.02})
    assert good["break_even_year"] is not None
    assert 1 <= good["break_even_year"] <= 5
    bad = service.simulate(
        {**BASE, "annual_growth_mean": -0.2, "annual_growth_vol": 0.02, "gross_yield": 0}
    )
    assert bad["break_even_year"] is None
    assert bad["prob_loss"] > 0.99


def test_real_return_below_nominal_with_inflation() -> None:
    out = service.simulate(BASE)
    assert out["real_return_pct"] < out["total_return_pct"]["p50"]
    assert out["prob_real_loss"] >= out["prob_loss"]


RISK: dict[str, Any] = {
    "developer_on_time_rate": 0.9,
    "years_to_delivery": 2,
    "liquidity_tier": 1,
    "price_egp": 1_000_000,
    "value_p10": 1_100_000,
    "value_p50": 1_500_000,
    "prob_real_loss": 0.1,
}


def _levels(**changes: Any) -> dict[str, str]:
    out = service.risk_summary({**RISK, **changes})
    return {i["kind"]: i["level"] for i in out["items"]}


def test_risk_thresholds() -> None:
    assert _levels() == {
        "delivery": "low",
        "liquidity": "low",
        "price": "low",
        "currency_inflation": "low",
    }
    assert _levels(developer_on_time_rate=0.7)["delivery"] == "medium"
    assert _levels(developer_on_time_rate=0.5)["delivery"] == "high"
    assert _levels(years_to_delivery=4)["delivery"] == "medium"
    assert _levels(years_to_delivery=0, developer_on_time_rate=0.1)["delivery"] == "low"
    assert _levels(liquidity_tier=3)["liquidity"] == "high"
    assert _levels(value_p10=900_000)["price"] == "medium"
    assert _levels(value_p10=800_000, value_p50=900_000)["price"] == "high"
    assert _levels(prob_real_loss=0.3)["currency_inflation"] == "medium"
    assert _levels(prob_real_loss=0.5)["currency_inflation"] == "high"
    item = service.risk_summary(RISK)["items"][0]
    assert item["explanation_en"] and item["explanation_ar"]


def test_validation_error() -> None:
    with pytest.raises(ScenarioValidationError):
        service.simulate({**BASE, "horizon_years": 0})
    with pytest.raises(ScenarioValidationError):
        service.risk_summary({**RISK, "liquidity_tier": 4})


@pytest.fixture
def client() -> Iterator[TestClient[Any]]:
    app = Litestar(route_handlers=[build_scenarios_router(service)])
    with TestClient(app=app) as c:
        yield c


def test_api_ok(client: TestClient[Any]) -> None:
    r = client.post("/scenarios/simulate", json=BASE)
    assert r.status_code == 200
    assert r.json()["value_at_horizon"]["p50"] > 0
    r = client.post("/scenarios/risk", json=RISK)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 4


def test_api_bad_input(client: TestClient[Any]) -> None:
    assert client.post("/scenarios/simulate", json={"price_egp": -1}).status_code == 400
    assert client.post("/scenarios/risk", json={**RISK, "liquidity_tier": 9}).status_code == 400
