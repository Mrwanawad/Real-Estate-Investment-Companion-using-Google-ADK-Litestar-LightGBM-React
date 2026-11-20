"""Load the demo data into Postgres. Idempotent.

Inventory (developers, projects, units, payment plans) comes from the real listings in
demo_data/listings (see scripts/import_listings.py), or from demo_data/synthetic with
--synthetic. Areas, price indices, rentals, macro series and the simulated brokers always come
from demo_data/synthetic.

Usage: python scripts/seed.py [DATABASE_URL] [--synthetic]
"""

import argparse
import csv
import json
import statistics
from pathlib import Path

from sqlalchemy import Connection, create_engine, text

from reic.shared.config import Settings

ROOT = Path(__file__).resolve().parent.parent / "demo_data"
DATA = ROOT / "synthetic"
LISTINGS = ROOT / "listings"
INVENTORY = {"developers", "projects", "units", "payment_plans"}
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


def seed(database_url: str, *, synthetic: bool = False) -> dict[str, int]:
    engine = create_engine(_sync_url(database_url))
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(t for t, _ in reversed(TABLES))} CASCADE"))
        for table, filename in TABLES:
            folder = LISTINGS if table in INVENTORY and not synthetic else DATA
            columns, rows = _rows(folder / filename)
            if table == "rental_listings" and not synthetic:
                rows = _rescale_rents(rows)
            names = ", ".join(columns)
            params = ", ".join(f"CAST(:{c} AS {_cast(table, c)})" for c in columns)
            conn.execute(text(f"INSERT INTO {table} ({names}) VALUES ({params})"), rows)
            counts[table] = len(rows)
        counts["brokers"] = _seed_brokers(conn)
    engine.dispose()
    return counts


def _price_per_m2(folder: Path) -> dict[str, float]:
    """Median asking price per m2 by area for the units in `folder`."""
    _, projects = _rows(folder / "projects.csv")
    area_of = {p["id"]: p["area_id"] for p in projects}
    _, units = _rows(folder / "units.csv")
    by_area: dict[str, list[float]] = {}
    for u in units:
        ppm = float(u["price_egp"]) / float(u["bua_m2"])  # type: ignore[arg-type]
        by_area.setdefault(str(area_of[u["project_id"]]), []).append(ppm)
    return {area: statistics.median(values) for area, values in by_area.items()}


def _rescale_rents(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """The synthetic rents were generated against synthetic prices. Scale them per area to the
    real listing price level, so rental yields keep the area's assumed yield."""
    real, synthetic = _price_per_m2(LISTINGS), _price_per_m2(DATA)
    out = []
    for row in rows:
        area = str(row["area_id"])
        ratio = real.get(area, synthetic[area]) / synthetic[area]
        rent = round(float(row["monthly_rent_egp"]) * ratio / 100) * 100  # type: ignore[arg-type]
        out.append({**row, "monthly_rent_egp": str(max(rent, 500))})
    return out


def _seed_brokers(conn: Connection) -> int:
    brokers = json.loads((DATA / "brokers.json").read_text(encoding="utf-8"))
    conn.execute(text("DELETE FROM brokers"))
    conn.execute(
        text(
            "INSERT INTO brokers (id, name, phone, email, languages, area_ids, simulated) "
            "VALUES (:id, :name, :phone, :email, CAST(:languages AS jsonb), "
            "CAST(:areas AS jsonb), true)"
        ),
        [
            {
                **b,
                "languages": json.dumps(b["languages"]),
                "areas": json.dumps(b["areas"], ensure_ascii=False),
            }
            for b in brokers
        ],
    )
    return len(brokers)


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
    parser = argparse.ArgumentParser()
    parser.add_argument("database_url", nargs="?", default=None)
    parser.add_argument("--synthetic", action="store_true", help="synthetic inventory")
    args = parser.parse_args()
    url = args.database_url or Settings().database_url
    for table, count in seed(url, synthetic=args.synthetic).items():
        print(f"{table:18} {count:6}")
