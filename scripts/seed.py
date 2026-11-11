"""Load the synthetic demo data (demo_data/synthetic/*.csv) into Postgres. Idempotent.

Usage: python scripts/seed.py [DATABASE_URL]   (defaults to Settings().database_url)
"""

import csv
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from reic.shared.config import Settings

DATA = Path(__file__).resolve().parent.parent / "demo_data" / "synthetic"
# Parents first; truncation runs in reverse.
TABLES = [
    ("areas", "areas.csv"),
    ("developers", "developers.csv"),
    ("projects", "projects.csv"),
    ("units", "units.csv"),
    ("payment_plans", "payment_plans.csv"),
    ("area_price_index", "area_price_index.csv"),
    ("rental_listings", "rental_listings.csv"),
    ("macro_monthly", "macro_monthly.csv"),
]
_BOOL = {"true": True, "false": False, "1": True, "0": False}


def _sync_url(url: str) -> str:
    return "postgresql+psycopg://" + url.split("://", 1)[1]


def _rows(path: Path) -> tuple[list[str], list[dict[str, object]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for row in reader:
            rows.append(
                {k: _BOOL.get(v.lower(), v) if k == "furnished" else v for k, v in row.items()}
            )
        return list(reader.fieldnames or []), rows


def seed(database_url: str) -> dict[str, int]:
    engine = create_engine(_sync_url(database_url))
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(t for t, _ in reversed(TABLES))} CASCADE"))
        for table, filename in TABLES:
            columns, rows = _rows(DATA / filename)
            names = ", ".join(columns)
            params = ", ".join(f"CAST(:{c} AS {_cast(table, c)})" for c in columns)
            conn.execute(text(f"INSERT INTO {table} ({names}) VALUES ({params})"), rows)
            counts[table] = len(rows)
    engine.dispose()
    return counts


def _cast(table: str, column: str) -> str:
    if column in {"month", "listing_date"}:
        return "date"
    if column == "furnished":
        return "boolean"
    if column in {
        "base_price_per_m2_2015",
        "liquidity_tier",
        "launch_year",
        "delivery_year",
        "bedrooms",
        "floor",
        "years",
        "price_egp",
        "monthly_rent_egp",
    } or (column == "id" and table == "rental_listings"):
        return "bigint"
    if column in {
        "gross_rental_yield_base",
        "on_time_delivery_rate",
        "bua_m2",
        "garden_m2",
        "down_payment_pct",
        "delivery_payment_pct",
        "maintenance_pct",
        "cash_discount_pct",
        "index_level",
        "avg_price_per_m2",
        "cpi_yoy_pct",
        "egp_per_usd",
        "cbe_deposit_rate",
        "cbe_lending_rate",
    }:
        return "double precision"
    return "text"


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else Settings().database_url
    for table, count in seed(url).items():
        print(f"{table:18} {count:6}")
