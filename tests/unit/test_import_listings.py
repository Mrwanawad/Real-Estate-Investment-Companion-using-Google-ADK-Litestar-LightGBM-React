import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import import_listings  # noqa: E402


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "url": "https://www.propertyfinder.eg/en/plp/buy/apartment-for-sale-x-7817046.html",
        "price": "12,652,000",
        "description": "Fully finished, 10% down over 8 years, delivery 2027, 3rd floor",
        "location": "Taj City, 5th Settlement Compounds, The 5th Settlement, New Cairo City, Cairo",
        "type": "Apartment",
        "size": "1,787 sqft / 166 sqm",
        "bedrooms": "3+ Maid",
        "bathrooms": "2",
        "available_from": "26 Aug 2025",
        "payment_method": "Installments",
        "down_payment": "",
    }
    return {**row, **overrides}


def test_listing_becomes_unit_project_and_plan() -> None:
    tables = import_listings.convert([_row()])
    unit = tables["units"][0]
    assert unit["code"] == "PF-7817046" and unit["type"] == "apartment"
    assert (unit["bedrooms"], unit["bua_m2"], unit["price_egp"]) == (3, 166.0, 12_652_000)
    assert (unit["finishing"], unit["delivery_year"], unit["floor"]) == ("fully", 2027, 3)
    assert str(unit["project_id"]).startswith("NC-")
    plan = tables["payment_plans"][0]
    assert (plan["down_payment_pct"], plan["years"]) == (0.1, 8)


def test_unmapped_implausible_and_duplicate_listings_are_dropped() -> None:
    rows = [
        _row(),
        _row(),  # same listing id
        _row(url="https://x/apartment-1.html", location="Somewhere, Hurghada, Red Sea"),
        _row(url="https://x/apartment-2.html", price="1,000"),
        _row(url="https://x/land-3.html", type="Land"),
    ]
    tables = import_listings.convert(rows)
    assert len(tables["units"]) == 1


def test_cash_listing_gets_a_cash_plan() -> None:
    tables = import_listings.convert([_row(payment_method="Cash", description="ready to move")])
    assert [p["name"] for p in tables["payment_plans"]] == ["Cash"]
    assert tables["units"][0]["delivery_year"] == import_listings.LISTED_YEAR
