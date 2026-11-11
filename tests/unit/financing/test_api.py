from collections.abc import Iterator
from decimal import Decimal as D
from typing import Any

import pytest
from litestar.testing import TestClient

from reic.bootstrap.app import create_app


@pytest.fixture
def client() -> Iterator[TestClient[Any]]:
    with TestClient(app=create_app()) as test_client:
        yield test_client


def test_installments_ok(client: TestClient[Any]) -> None:
    response = client.post(
        "/financing/installments",
        json={"price_egp": "3000000", "down_payment_pct": 0.1, "years": 7},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["installment_count"] == 28
    assert body["total_nominal"] == "3000000.00"
    assert body["payments"][-1] == {"index": 28, "month": 84, "kind": "final", "amount": "96428.61"}


def test_mortgage_ok(client: TestClient[Any]) -> None:
    response = client.post(
        "/financing/mortgage",
        json={"price_egp": 1000000, "down_payment_pct": 0, "annual_rate_pct": 0.12, "years": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_payment"] == "14347.09"
    assert len(body["rows"]) == 120
    assert body["rows"][-1]["balance"] == "0.00"


def test_compare_ok(client: TestClient[Any]) -> None:
    response = client.post(
        "/financing/compare",
        json={
            "price_egp": "1000000",
            "discount_rate_pct": "0.20",
            "cash_discount_pct": "0.05",
            "installment_plans": [
                {"label": "1y plan", "down_payment_pct": "0.1", "years": 1, "frequency": "annual"}
            ],
            "mortgages": [
                {
                    "label": "market",
                    "down_payment_pct": "0.2",
                    "annual_rate_pct": "0.25",
                    "years": 10,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [o["label"] for o in body["options"]] == ["Cash", "1y plan", "market"]
    assert body["cheapest_label"] == "1y plan"
    assert D(body["options"][1]["present_value"]) == D("850000.00")
    assert body["notes"][0]["code"] == "cheapest_by_pv"
    assert "discount_rate_annual" in body["assumptions"]


def test_down_payment_above_one_is_400_with_message(client: TestClient[Any]) -> None:
    response = client.post(
        "/financing/installments",
        json={"price_egp": "1000000", "down_payment_pct": 1.5, "years": 5},
    )
    assert response.status_code == 400
    assert "down_payment_pct must be between 0 and 1" in response.json()["detail"]


def test_missing_and_unknown_fields_are_400_with_field_names(client: TestClient[Any]) -> None:
    response = client.post("/financing/mortgage", json={"price_egp": "100", "years": 5, "bogus": 1})
    assert response.status_code == 400
    fields = {e["field"] for e in response.json()["extra"]}
    assert {"down_payment_pct", "annual_rate_pct", "bogus"} <= fields


def test_bad_frequency_and_type_errors_are_400(client: TestClient[Any]) -> None:
    bad_frequency = client.post(
        "/financing/installments",
        json={"price_egp": "1000", "down_payment_pct": 0.1, "years": 1, "frequency": "weekly"},
    )
    assert bad_frequency.status_code == 400
    bad_type = client.post(
        "/financing/installments",
        json={"price_egp": "abc", "down_payment_pct": 0.1, "years": 1},
    )
    assert bad_type.status_code == 400


def test_compare_domain_errors_are_400(client: TestClient[Any]) -> None:
    duplicate = client.post(
        "/financing/compare",
        json={
            "price_egp": "1000000",
            "discount_rate_pct": "0.2",
            "installment_plans": [
                {"label": "Cash", "down_payment_pct": "0.1", "years": 1, "frequency": "annual"}
            ],
        },
    )
    assert duplicate.status_code == 400
    assert "unique" in duplicate.json()["detail"]
    bad_rate = client.post(
        "/financing/compare", json={"price_egp": "1000000", "discount_rate_pct": "20"}
    )
    assert bad_rate.status_code == 400
    assert "discount_rate_pct must be between 0 and 1" in bad_rate.json()["detail"]


def test_malformed_json_is_400(client: TestClient[Any]) -> None:
    response = client.post(
        "/financing/mortgage", content=b"{nope", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400
