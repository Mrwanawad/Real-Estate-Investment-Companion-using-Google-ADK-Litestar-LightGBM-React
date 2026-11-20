"""Turn a public Egyptian listings dataset into the app's inventory tables.

Source: "Egyptian Real Estate Listings" (Kaggle, hassankhaled21), ~20k for-sale listings
collected from PropertyFinder Egypt in August 2025, licensed CC BY-SA 4.0. The download
needs no account.

Writes demo_data/listings/{developers,projects,units,payment_plans}.csv in the same shape as
the synthetic CSVs, so scripts/seed.py loads either. Listings outside the 12 modelled areas,
non-residential types and implausible prices or sizes are dropped. Fields the source lacks are
filled with labelled assumptions (see ASSUMPTIONS and demo_data/listings/README.md).

Usage: python scripts/import_listings.py [--csv PATH]   (downloads the dataset when omitted)
"""

import argparse
import csv
import hashlib
import io
import re
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo_data" / "listings"
DATASET_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/hassankhaled21/egyptian-real-estate-listings"
)
LISTED_YEAR = 2025

# Fields the listings don't carry. Shown in the README and in the app's notes.
ASSUMPTIONS = {
    "developer": "not listed; one 'Developer not listed' record, tier B, 75% on-time rate",
    "installment_years": "parsed from the description, else 7 years, quarterly",
    "down_payment_pct": "listing down payment / price, else parsed '% down', else 10%",
    "delivery_year": "parsed from the description, else ready (2025)",
    "finishing": "parsed from the description, else semi-finished",
    "floor": "parsed from the description, else 1 (0 for villas and houses)",
    "maintenance_pct": "8% of price, a common Egyptian compound deposit",
}

# First match wins; checked against the full location string.
AREA_RULES: list[tuple[str, str]] = [
    (r"Alamein", "AL"),
    (r"North Coast", "SH"),
    (r"Sokhna", "SK"),
    (r"Mostakbal", "MS"),
    (r"Madinaty", "MD"),
    (r"New Capital", "NA"),
    (r"Sheikh Zayed|New Zayed", "SZ"),
    (r"6 October", "OC"),
    (r"New Cairo", "NC"),
    (r"Maadi", "MA"),
    (r"Zamalek", "ZM"),
    (r"(?<!New )Heliopolis", "HE"),
]
TYPES = {
    "Apartment": "apartment",
    "Penthouse": "apartment",
    "Hotel Apartment": "apartment",
    "Duplex": "duplex",
    "Townhouse": "townhouse",
    "Twin House": "twin_house",
    "Villa": "villa",
    "iVilla": "villa",
    "Chalet": "chalet",
    "Cabin": "chalet",
}
HOUSES = {"villa", "townhouse", "twin_house"}
DEVELOPER_ID = "DNL"


def _int(text: str | None) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _sqm(size: str) -> float | None:
    match = re.search(r"([\d,]+)\s*sqm", size or "")
    return float(match.group(1).replace(",", "")) if match else None


def _bedrooms(text: str) -> int | None:
    if (text or "").strip().lower() == "studio":
        return 1
    match = re.match(r"\s*(\d+)", text or "")
    return int(match.group(1)) if match else None


def _finishing(desc: str) -> str:
    if re.search(r"fully[\s-]*finish|fully furnished|ultra super lux", desc):
        return "fully"
    if re.search(r"core\s*(&|and)?\s*shell", desc):
        return "core_shell"
    return "semi"


def _delivery(desc: str) -> int:
    match = re.search(r"deliver\w*\D{0,20}(20[2-3]\d)", desc)
    if match:
        return max(LISTED_YEAR, int(match.group(1)))
    return LISTED_YEAR


def _floor(desc: str, unit_type: str) -> int:
    if unit_type in HOUSES:
        return 0
    if re.search(r"ground floor", desc):
        return 0
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+floor", desc)
    return min(int(match.group(1)), 40) if match else 1


def _garden(desc: str) -> float:
    match = re.search(r"garden\D{0,12}(\d{2,4})\s*(?:m|sqm|meter)", desc)
    return float(match.group(1)) if match else 0.0


def _plan_terms(desc: str, price: int, down_egp: int | None) -> tuple[float, int]:
    if down_egp and 0 < down_egp < price:
        down = down_egp / price
    elif match := re.search(r"(\d{1,2}(?:\.\d)?)\s*%\s*(?:down|dp|deposit)", desc):
        down = float(match.group(1)) / 100
    else:
        down = 0.10
    years_match = re.search(r"(?:over|on|up to|installments?\D{0,15})\s*(\d{1,2})\s*years?", desc)
    years = int(years_match.group(1)) if years_match else 7
    return round(min(max(down, 0.0), 0.5), 2), min(max(years, 2), 12)


def _read_source(path: Path | None) -> list[dict[str, str]]:
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(DATASET_URL, timeout=120) as response:  # noqa: S310
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        name = next(n for n in archive.namelist() if n.endswith(".csv"))
        text = archive.read(name).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _area(location: str) -> str | None:
    for pattern, area_id in AREA_RULES:
        if re.search(pattern, location):
            return area_id
    return None


def convert(rows: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    units: list[dict[str, object]] = []
    projects: dict[str, dict[str, object]] = {}
    terms: dict[str, set[tuple[float, int]]] = defaultdict(set)
    cash_projects: set[str] = set()
    seen: set[str] = set()
    for row in rows:
        unit_type = TYPES.get((row.get("type") or "").strip())
        location = row.get("location") or ""
        area_id = _area(location)
        price = _int(row.get("price"))
        bua = _sqm(row.get("size", ""))
        bedrooms = _bedrooms(row.get("bedrooms", ""))
        listing = re.search(r"-(\d+)\.html", row.get("url") or "")
        if not (unit_type and area_id and price and bua and bedrooms and listing):
            continue
        per_m2 = price / bua
        if not (25 <= bua <= 2000 and 500_000 <= price <= 300_000_000):
            continue
        if not 5_000 <= per_m2 <= 600_000:  # typos, rentals and totals listed as prices
            continue
        code = f"PF-{listing.group(1)}"
        if code in seen:
            continue
        seen.add(code)
        compound = location.split(",")[0].strip()
        project_id = f"{area_id}-" + hashlib.sha1(compound.encode()).hexdigest()[:8]
        desc = (row.get("description") or "").lower()
        delivery = _delivery(desc)
        project = projects.setdefault(
            project_id,
            {
                "id": project_id,
                "name_en": compound[:120],
                "name_ar": compound[:120],
                "area_id": area_id,
                "developer_id": DEVELOPER_ID,
                "launch_year": LISTED_YEAR - 2,
                "delivery_year": delivery,
                "amenities": "",
            },
        )
        project["delivery_year"] = max(int(project["delivery_year"]), delivery)  # type: ignore[call-overload]
        if (row.get("payment_method") or "").strip().lower() == "installments":
            terms[project_id].add(_plan_terms(desc, price, _int(row.get("down_payment"))))
        else:
            cash_projects.add(project_id)
        units.append(
            {
                "code": code,
                "project_id": project_id,
                "type": unit_type,
                "bedrooms": min(bedrooms, 10),
                "bua_m2": bua,
                "garden_m2": _garden(desc),
                "floor": _floor(desc, unit_type),
                "finishing": _finishing(desc),
                "delivery_year": delivery,
                "status": "available",
                "price_egp": price,
                "view": "not_listed",
                "source_url": row["url"].strip(),
            }
        )

    plans: list[dict[str, object]] = []
    for project_id in sorted(projects):
        chosen = sorted(terms.get(project_id, set()), key=lambda t: (t[1], t[0]))
        if len(chosen) > 3:  # keep the shortest, the median and the longest
            chosen = [chosen[0], chosen[len(chosen) // 2], chosen[-1]]
        for n, (down, years) in enumerate(chosen, start=1):
            plans.append(
                {
                    "id": f"{project_id}-I{n}",
                    "project_id": project_id,
                    "name": f"{down:.0%} down / {years} years quarterly",
                    "down_payment_pct": down,
                    "years": years,
                    "frequency": "quarterly",
                    "delivery_payment_pct": 0.0,
                    "maintenance_pct": 0.08,
                    "cash_discount_pct": 0.0,
                }
            )
        if project_id in cash_projects or not chosen:
            plans.append(
                {
                    "id": f"{project_id}-C",
                    "project_id": project_id,
                    "name": "Cash",
                    "down_payment_pct": 1.0,
                    "years": 1,
                    "frequency": "quarterly",
                    "delivery_payment_pct": 0.0,
                    "maintenance_pct": 0.08,
                    "cash_discount_pct": 0.0,
                }
            )
    developers = [
        {
            "id": DEVELOPER_ID,
            "name_en": "Developer not listed",
            "tier": "B",
            "on_time_delivery_rate": 0.75,
        }
    ]
    return {
        "developers": developers,
        "projects": list(projects.values()),
        "units": units,
        "payment_plans": plans,
    }


def _write(name: str, rows: list[dict[str, object]]) -> None:
    with (OUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, help="local copy of egypt_real_estate_listings.csv")
    args = parser.parse_args()
    source = _read_source(args.csv)
    tables = convert(source)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        _write(name, rows)
    units = tables["units"]
    by_area: dict[str, int] = defaultdict(int)
    for unit in units:
        by_area[str(unit["project_id"]).split("-")[0]] += 1
    median = statistics.median(int(u["price_egp"]) for u in units)  # type: ignore[call-overload]
    print(f"source rows {len(source)}, kept units {len(units)}, projects {len(tables['projects'])}")
    print(f"plans {len(tables['payment_plans'])}, median price {median:,.0f} EGP")
    print("units per area:", dict(sorted(by_area.items())))


if __name__ == "__main__":
    main()
