"""Row-to-domain mapping shared by the CSV and SQL data sources."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from reic.modules.market.domain.models import (
    IndexSeries,
    MarketData,
    RentalListing,
    RentFeatures,
    UnitFeatures,
    UnitSale,
)

Row = Mapping[str, Any]


def _date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _bool(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "t"}


def build_market_data(
    index_rows: Iterable[Row], unit_rows: Iterable[Row], rental_rows: Iterable[Row]
) -> MarketData:
    """`unit_rows` are units already joined with project area_id and developer tier."""
    points: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for r in index_rows:
        points[str(r["area_id"])].append((_date(r["month"]), float(r["index_level"])))
    index = {}
    for area_id, pts in points.items():
        pts.sort()
        index[area_id] = IndexSeries(
            area_id, tuple(m for m, _ in pts), tuple(level for _, level in pts)
        )

    sales = tuple(
        UnitSale(
            features=UnitFeatures(
                area_id=r["area_id"],
                type=r["type"],
                bedrooms=int(r["bedrooms"]),
                bua_m2=float(r["bua_m2"]),
                garden_m2=float(r["garden_m2"]),
                floor=int(r["floor"]),
                finishing=r["finishing"],
                delivery_year=int(r["delivery_year"]),
                developer_tier=r["developer_tier"],
            ),
            price_egp=float(r["price_egp"]),
        )
        for r in unit_rows
    )
    rentals = tuple(
        RentalListing(
            listing_date=_date(r["listing_date"]),
            features=RentFeatures(
                area_id=r["area_id"],
                type=r["type"],
                bedrooms=int(r["bedrooms"]),
                bua_m2=float(r["bua_m2"]),
                finishing=r["finishing"],
                furnished=_bool(r["furnished"]),
            ),
            monthly_rent_egp=float(r["monthly_rent_egp"]),
        )
        for r in rental_rows
    )
    return MarketData(index=index, unit_sales=sales, rentals=rentals)
