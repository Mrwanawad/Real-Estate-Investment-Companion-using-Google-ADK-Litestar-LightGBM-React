"""Generate the SYNTHETIC demo dataset into demo_data/synthetic/.

Deterministic: the same --seed and size options always produce byte-identical CSVs (see
manifest.json for row counts and sha256). Only numpy and the standard library are used.

Everything written here is invented, except that the macro series are anchored to real public
indices in demo_data/public/ (World Bank annual CPI and EGP/USD, the current CBE rate and two
recent monthly CPI points). Monthly macro values are interpolated or synthetic and are NOT
official statistics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC = ROOT / "demo_data" / "public"
DEFAULT_OUT = ROOT / "demo_data" / "synthetic"

START_YEAR = 2015
N_MONTHS = 11 * 12 + 10  # 2015-01 .. 2026-10
LAST = N_MONTHS - 1

MACRO_PROVENANCE = "cpi_fx=interpolated_from_worldbank_annual;cbe=synthetic_anchored_to_current"

# id, name_en, name_ar, type, base price per m2 in 2015 (EGP), liquidity tier, yield offset
AREAS: list[tuple[str, str, str, str, int, int, float]] = [
    ("NC", "New Cairo", "القاهرة الجديدة", "urban", 11000, 1, 0.000),
    ("SZ", "Sheikh Zayed", "الشيخ زايد", "urban", 10000, 1, 0.001),
    ("OC", "6th of October", "السادس من أكتوبر", "urban", 7500, 2, 0.003),
    ("SH", "North Coast", "الساحل الشمالي", "coastal", 14000, 2, 0.000),
    ("NA", "New Administrative Capital", "العاصمة الإدارية الجديدة", "urban", 8000, 2, 0.002),
    ("MS", "Mostakbal City", "مستقبل سيتي", "urban", 6500, 3, 0.003),
    ("MD", "Madinaty", "مدينتي", "urban", 9500, 1, 0.002),
    ("MA", "Maadi", "المعادي", "urban", 14000, 1, -0.002),
    ("ZM", "Zamalek", "الزمالك", "urban", 28000, 1, -0.006),
    ("AL", "New Alamein", "العلمين الجديدة", "coastal", 12000, 2, 0.002),
    ("SK", "Ain Sokhna", "العين السخنة", "coastal", 9000, 3, 0.004),
    ("HE", "Heliopolis", "مصر الجديدة", "urban", 12000, 1, -0.001),
]
YIELD_BASE = {"urban": 0.050, "coastal": 0.038}
LIQUIDITY_PREMIUM = {1: 0.0004, 2: 0.0001, 3: -0.0002}

# Fictional developers. Names are invented and do not refer to real companies.
DEVELOPERS = [
    ("Kemet Vista Developments", "A"),
    ("Tamarisk Estates", "A"),
    ("Nilufar Homes", "A"),
    ("Zephyra Group", "A"),
    ("Solara Living", "B"),
    ("Meridian Crest", "B"),
    ("Aurelia Urban", "B"),
    ("Sandrose Developments", "B"),
    ("Cobalt Nile Properties", "B"),
    ("Wadi Bloom Developments", "B"),
    ("Ibis Gate Properties", "C"),
    ("Saffron Bay Developments", "C"),
    ("Alder Horizon", "C"),
    ("Dunemark Group", "C"),
    ("Lumen Habitat", "C"),
]
ON_TIME_RANGE = {"A": (0.85, 0.97), "B": (0.65, 0.85), "C": (0.40, 0.68)}
TIER_PRICE = {"A": 1.12, "B": 1.0, "C": 0.90}

NAME_A = [
    ("Lotus", "اللوتس"),
    ("Oasis", "الواحة"),
    ("Horizon", "الأفق"),
    ("Crescent", "الهلال"),
    ("Falcon", "الصقر"),
    ("Jasmine", "الياسمين"),
    ("Amber", "العنبر"),
    ("Sapphire", "الياقوت"),
    ("Olive", "الزيتون"),
    ("Dune", "الكثبان"),
    ("Pearl", "اللؤلؤ"),
    ("Nile", "النيل"),
    ("Sunrise", "الشروق"),
    ("Breeze", "النسيم"),
]
NAME_B = [
    ("Gardens", "حدائق"),
    ("Heights", "مرتفعات"),
    ("Bay", "خليج"),
    ("Village", "قرية"),
    ("Views", "إطلالات"),
    ("Square", "ميدان"),
    ("Hills", "تلال"),
    ("Walk", "ممشى"),
]
AMENITIES = [
    "pool",
    "gym",
    "clubhouse",
    "mall",
    "school",
    "golf",
    "lagoon",
    "security_24h",
    "underground_parking",
    "kids_area",
    "mosque",
    "medical_center",
]

UNIT_TYPES = ["apartment", "duplex", "townhouse", "twin_house", "villa", "chalet"]
TYPE_PRICE = {
    "apartment": 1.0,
    "duplex": 1.08,
    "townhouse": 1.15,
    "twin_house": 1.22,
    "villa": 1.35,
    "chalet": 1.10,
}
TYPE_YIELD = {
    "apartment": 1.0,
    "duplex": 0.95,
    "townhouse": 0.92,
    "twin_house": 0.90,
    "villa": 0.88,
    "chalet": 1.05,
}
TYPE_MIX_URBAN = [0.55, 0.10, 0.12, 0.08, 0.15, 0.0]
TYPE_MIX_COASTAL = [0.25, 0.08, 0.10, 0.10, 0.12, 0.35]
TYPE_MIX_CENTRAL = [0.86, 0.08, 0.0, 0.0, 0.06, 0.0]  # Maadi, Zamalek, Heliopolis
CENTRAL = {"MA", "ZM", "HE"}
FINISHING_PRICE = {"core_shell": 0.88, "semi": 1.0, "fully": 1.12}
VIEWS_URBAN = (
    ["garden", "street", "pool", "landscape", "golf", "city"],
    [0.3, 0.2, 0.15, 0.2, 0.05, 0.1],
)
VIEWS_COASTAL = (["sea", "lagoon", "pool", "garden", "landscape"], [0.3, 0.2, 0.2, 0.2, 0.1])
VIEW_PRICE = {
    "sea": 1.12,
    "lagoon": 1.08,
    "golf": 1.08,
    "garden": 1.04,
    "pool": 1.04,
    "landscape": 1.03,
    "city": 1.0,
    "street": 0.97,
}

# Devaluation level jumps in the area price index (month -> fractional jump).
JUMPS = {"2016-11": 0.12, "2022-03": 0.06, "2022-10": 0.08, "2023-01": 0.07, "2024-03": 0.15}

# CBE deposit rate changes (month -> change in percentage points). The path is synthetic and
# anchored so that it ends exactly at the real 20.00 / 21.00.
CBE_CHANGES = {
    "2015-12": 0.5,
    "2016-03": 0.5,
    "2016-11": 3.0,
    "2017-05": 2.0,
    "2017-07": 2.0,
    "2018-02": -1.0,
    "2018-03": -1.0,
    "2019-02": -1.0,
    "2019-09": -1.0,
    "2019-11": -1.0,
    "2020-03": -3.0,
    "2022-03": 1.0,
    "2022-05": 2.0,
    "2022-10": 2.0,
    "2022-12": 3.0,
    "2023-02": 2.0,
    "2023-03": 2.0,
    "2023-05": 0.5,
    "2023-08": 1.0,
    "2024-03": 6.0,
    "2025-04": -2.25,
    "2025-05": -1.0,
    "2025-08": -1.0,
    "2025-10": -1.0,
    "2026-02": -1.0,
    "2026-04": -1.0,
    "2026-10": -1.0,
}


def month_label(i: int) -> str:
    return f"{START_YEAR + i // 12}-{i % 12 + 1:02d}"


def month_date(i: int) -> str:
    return f"{month_label(i)}-01"


def month_index(label: str) -> int:
    y, m = label.split("-")
    return (int(y) - START_YEAR) * 12 + int(m) - 1


def write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- macro


def build_macro(public: Path) -> list[list[object]]:
    cpi_rows = read_csv(public / "cpi_inflation_annual_worldbank.csv")
    fx_rows = read_csv(public / "egp_usd_annual_worldbank.csv")
    monthly_cpi = read_csv(public / "cpi_inflation.csv")
    cbe = read_csv(public / "cbe_rates.csv")[-1]
    deposit_now = float(cbe["overnight_deposit_rate"])
    lending_now = float(cbe["overnight_lending_rate"])

    # Annual averages are placed at mid-year (July).
    cpi_x = [(int(r["year"]) - START_YEAR) * 12 + 6 for r in cpi_rows]
    cpi_y = [float(r[next(k for k in r if k.startswith("inflation"))]) for r in cpi_rows]
    for r in monthly_cpi:  # real recent monthly points anchor the 2026 tail
        cpi_x.append(month_index(r["month"]))
        cpi_y.append(float(r["urban_headline_inflation_yoy_pct"]))
    order = np.argsort(cpi_x)
    cpi_x = [cpi_x[i] for i in order]
    cpi_y = [cpi_y[i] for i in order]

    fx_x = [(int(r["year"]) - START_YEAR) * 12 + 6 for r in fx_rows]
    fx_y = [float(r[next(k for k in r if k.startswith("egp_per_usd"))]) for r in fx_rows]

    months = np.arange(N_MONTHS)
    cpi = np.interp(months, cpi_x, cpi_y)
    fx = np.exp(np.interp(months, fx_x, np.log(fx_y)))

    deposit = np.zeros(N_MONTHS)
    level = deposit_now - sum(CBE_CHANGES.values())
    for i in range(N_MONTHS):
        level += CBE_CHANGES.get(month_label(i), 0.0)
        deposit[i] = level
    assert abs(deposit[-1] - deposit_now) < 1e-9, "synthetic CBE path must end at the real rate"
    spread = lending_now - deposit_now

    return [
        [
            month_date(i),
            f"{cpi[i]:.2f}",
            f"{fx[i]:.4f}",
            f"{deposit[i]:.2f}",
            f"{deposit[i] + spread:.2f}",
            MACRO_PROVENANCE,
        ]
        for i in range(N_MONTHS)
    ]


# ---------------------------------------------------------------- dimensions


def build_areas() -> list[list[object]]:
    return [
        [aid, en, ar, kind, base, tier, f"{YIELD_BASE[kind] + offset:.4f}"]
        for aid, en, ar, kind, base, tier, offset in AREAS
    ]


def build_developers(rng: np.random.Generator) -> list[list[object]]:
    rows: list[list[object]] = []
    for i, (name, tier) in enumerate(DEVELOPERS, start=1):
        lo, hi = ON_TIME_RANGE[tier]
        rows.append([f"D{i:02d}", name, tier, f"{rng.uniform(lo, hi):.2f}"])
    return rows


def build_projects(
    rng: np.random.Generator, n_projects: int, developers: list[list[object]]
) -> list[list[object]]:
    area_ids = [a[0] for a in AREAS]
    assigned = list(area_ids) * 3
    assigned += [str(x) for x in rng.choice(area_ids, size=max(0, n_projects - len(assigned)))]
    assigned = assigned[:n_projects]
    rng.shuffle(assigned)
    name_pairs = [(a, b) for a in NAME_A for b in NAME_B]
    picks = rng.permutation(len(name_pairs))[:n_projects]
    dev_ids = [str(d[0]) for d in developers]
    dev_tier = {str(d[0]): str(d[2]) for d in developers}
    counters: dict[str, int] = {}
    rows: list[list[object]] = []
    for k in range(n_projects):
        area = str(assigned[k])
        counters[area] = counters.get(area, 0) + 1
        pid = f"{area}-P{counters[area]:02d}"
        (a_en, a_ar), (b_en, b_ar) = name_pairs[int(picks[k])]
        premium = area in {"ZM", "MA", "NC", "SZ", "SH"}
        tier_weight = {"A": 3.0 if premium else 1.5, "B": 2.0, "C": 1.0}
        weights = np.array([tier_weight[dev_tier[d]] for d in dev_ids])
        dev = str(rng.choice(dev_ids, p=weights / weights.sum()))
        launch = int(rng.integers(2019, 2027))
        delivery = launch + int(rng.integers(3, 7))
        amen = sorted(rng.choice(AMENITIES, size=int(rng.integers(3, 8)), replace=False))
        rows.append(
            [pid, f"{a_en} {b_en}", f"{b_ar} {a_ar}", area, dev, launch, delivery, "|".join(amen)]
        )
    return rows


def build_payment_plans(
    rng: np.random.Generator, projects: list[list[object]]
) -> list[list[object]]:
    rows: list[list[object]] = []
    for p in projects:
        pid = str(p[0])
        for n in range(1, int(rng.integers(1, 4)) + 1):
            dp = float(rng.choice([0.05, 0.10, 0.15, 0.20]))
            years = int(rng.integers(4, 11))
            freq = str(rng.choice(["monthly", "quarterly"], p=[0.4, 0.6]))
            delivery_pct = float(rng.choice([0.0, 0.05, 0.10]))
            maint = float(rng.choice([0.08, 0.09, 0.10]))
            raw_discount = float(np.clip(0.02 * years + rng.normal(0, 0.03), 0.02, 0.25))
            discount = 0.0 if rng.random() < 0.15 else raw_discount
            rows.append(
                [
                    f"{pid}-PP{n}",
                    pid,
                    f"{int(round(dp * 100))}% down / {years} years {freq}",
                    f"{dp:.2f}",
                    years,
                    freq,
                    f"{delivery_pct:.2f}",
                    f"{maint:.2f}",
                    f"{discount:.2f}",
                ]
            )
    return rows


# ---------------------------------------------------------------- price index


def build_area_index(
    rng: np.random.Generator, macro: list[list[object]]
) -> tuple[list[list[object]], np.ndarray]:
    cpi = np.array([float(r[1]) for r in macro]) / 100.0
    jump_by_month = np.zeros(N_MONTHS)
    for label, jump in JUMPS.items():
        i = month_index(label)
        jump_by_month[i] += 0.6 * jump
        if i + 1 < N_MONTHS:
            jump_by_month[i + 1] += 0.4 * jump
    season = 0.003 * np.sin(2 * np.pi * (np.arange(N_MONTHS) - 6) / 12)
    levels = np.zeros((len(AREAS), N_MONTHS))
    rows: list[list[object]] = []
    for a, (aid, _en, _ar, kind, base, tier, _y) in enumerate(AREAS):
        beta = rng.uniform(0.65, 0.85)
        premium = (0.0016 if kind == "coastal" else 0.0013) + LIQUIDITY_PREMIUM[tier]
        premium += rng.normal(0, 0.0003)
        jump_sens = rng.uniform(0.8, 1.25)
        sigma = rng.uniform(0.005, 0.009)
        eps = 0.0
        log_level = np.log(100.0)
        for i in range(N_MONTHS):
            eps = 0.45 * eps + sigma * rng.standard_normal()
            if i > 0:
                drift = beta * np.log1p(cpi[i]) / 12 + premium + season[i] + eps
                log_level += drift + jump_sens * jump_by_month[i]
            levels[a, i] = np.exp(log_level)
            rows.append(
                [month_date(i), aid, f"{levels[a, i]:.2f}", f"{base * levels[a, i] / 100:.0f}"]
            )
    rows.sort(key=lambda r: (str(r[1]), str(r[0])))
    return rows, levels


# ---------------------------------------------------------------- units & rentals


def sample_layout(rng: np.random.Generator, utype: str) -> tuple[int, float, float]:
    """Return bedrooms, built-up area and garden area for a unit type."""
    if utype == "apartment":
        beds = int(rng.choice([1, 2, 3, 4], p=[0.15, 0.40, 0.35, 0.10]))
        bua = {1: 65, 2: 100, 3: 145, 4: 195}[beds] * rng.uniform(0.9, 1.15)
        garden = 0.0
    elif utype == "duplex":
        beds = int(rng.choice([3, 4]))
        bua = rng.uniform(220, 300)
        garden = float(rng.uniform(0, 60)) if rng.random() < 0.4 else 0.0
    elif utype == "townhouse":
        beds = int(rng.choice([3, 4]))
        bua = rng.uniform(200, 260)
        garden = rng.uniform(40, 120)
    elif utype == "twin_house":
        beds = int(rng.choice([4, 5]))
        bua = rng.uniform(260, 340)
        garden = rng.uniform(100, 250)
    elif utype == "villa":
        beds = int(rng.choice([4, 5, 6]))
        bua = rng.uniform(300, 500)
        garden = rng.uniform(150, 500)
    else:  # chalet
        beds = int(rng.choice([1, 2, 3], p=[0.3, 0.5, 0.2]))
        bua = {1: 55, 2: 85, 3: 125}[beds] * rng.uniform(0.9, 1.1)
        garden = float(rng.uniform(0, 40)) if rng.random() < 0.3 else 0.0
    return beds, float(round(float(bua))), float(round(float(garden)))


def type_mix(area_id: str, kind: str) -> list[float]:
    if area_id in CENTRAL:
        return TYPE_MIX_CENTRAL
    return TYPE_MIX_COASTAL if kind == "coastal" else TYPE_MIX_URBAN


def rental_mix(area_id: str, kind: str) -> list[float]:
    if area_id in CENTRAL:
        return [0.92, 0.04, 0.0, 0.0, 0.04, 0.0]
    if kind == "coastal":
        return [0.30, 0.04, 0.04, 0.04, 0.06, 0.52]
    return [0.82, 0.05, 0.03, 0.03, 0.07, 0.0]


def build_units(
    rng: np.random.Generator,
    n_units: int,
    projects: list[list[object]],
    developers: list[list[object]],
    levels: np.ndarray,
) -> list[list[object]]:
    area_pos = {a[0]: i for i, a in enumerate(AREAS)}
    area_info = {a[0]: a for a in AREAS}
    dev_tier = {str(d[0]): str(d[2]) for d in developers}
    weights = rng.uniform(0.5, 1.5, size=len(projects))
    counts = rng.multinomial(n_units, weights / weights.sum())
    rows: list[list[object]] = []
    for p, count in zip(projects, counts, strict=True):
        pid, _en, _ar, area, dev, _launch, delivery, _amen = p
        info = area_info[str(area)]
        kind, base = info[3], info[4]
        ppm2 = base * levels[area_pos[str(area)], LAST] / 100.0 * TIER_PRICE[dev_tier[str(dev)]]
        views, view_p = VIEWS_COASTAL if kind == "coastal" else VIEWS_URBAN
        mix = type_mix(str(area), kind)
        for k in range(int(count)):
            utype = str(rng.choice(UNIT_TYPES, p=mix))
            beds, bua, garden = sample_layout(rng, utype)
            if utype in ("apartment", "duplex"):
                floor = int(rng.integers(0, 13))
            elif utype == "chalet":
                floor = int(rng.integers(0, 4))
            else:
                floor = 0
            fin_p = [0.15, 0.35, 0.50] if utype == "chalet" else [0.30, 0.35, 0.35]
            finishing = str(rng.choice(["core_shell", "semi", "fully"], p=fin_p))
            view = str(rng.choice(views, p=view_p))
            unit_delivery = int(delivery) + (1 if rng.random() < 0.15 else 0)
            offplan = max(0, unit_delivery - 2026)
            if utype in ("villa", "twin_house", "townhouse"):
                floor_mult = 1.0
            else:
                floor_mult = 0.96 if floor == 0 else 1 + 0.006 * floor
            value = (
                ppm2
                * (bua + 0.3 * garden)
                * TYPE_PRICE[utype]
                * FINISHING_PRICE[finishing]
                * floor_mult
                * VIEW_PRICE[view]
                * (1 - 0.015 * offplan)
                * float(rng.lognormal(0, 0.06))
            )
            price = int(round(value / 5000.0) * 5000)
            ready = unit_delivery <= 2026
            status = str(
                rng.choice(
                    ["available", "reserved", "sold"],
                    p=[0.40, 0.05, 0.55] if ready else [0.65, 0.10, 0.25],
                )
            )
            code = f"{pid}-{'ABCDEF'[k % 6]}-{floor:02d}{k // 6 + 1:02d}"
            rows.append(
                [
                    code,
                    pid,
                    utype,
                    beds,
                    int(bua),
                    int(garden),
                    floor,
                    finishing,
                    unit_delivery,
                    status,
                    price,
                    view,
                ]
            )
    return rows


def build_rentals(
    rng: np.random.Generator, n_listings: int, areas: list[list[object]], levels: np.ndarray
) -> list[list[object]]:
    first = month_index("2019-01")
    span = np.arange(first, N_MONTHS)
    month_p = 1 + (span - first) / 30.0
    month_p /= month_p.sum()
    area_p = np.array([1.5 if a[0] in {"NC", "SZ", "OC", "SH", "MA"} else 1.0 for a in AREAS])
    area_p /= area_p.sum()
    rows: list[list[object]] = []
    for n in range(1, n_listings + 1):
        a = int(rng.choice(len(AREAS), p=area_p))
        aid, _en, _ar, kind, base, _tier, _off = AREAS[a]
        m = int(rng.choice(span, p=month_p))
        day = int(rng.integers(1, 28))
        utype = str(rng.choice(UNIT_TYPES, p=rental_mix(aid, kind)))
        beds, bua, _garden = sample_layout(rng, utype)
        finishing = str(rng.choice(["fully", "semi", "core_shell"], p=[0.65, 0.30, 0.05]))
        wants_furnished = bool(rng.random() < (0.6 if kind == "coastal" else 0.3))
        furnished = wants_furnished and finishing == "fully"
        value = base * levels[a, m] / 100.0 * bua * TYPE_PRICE[utype] * FINISHING_PRICE[finishing]
        gross_yield = float(areas[a][6]) * TYPE_YIELD[utype] * (1.18 if furnished else 1.0)
        rent = value * gross_yield / 12 * float(rng.lognormal(0, 0.12))
        rows.append(
            [
                n,
                f"{month_label(m)}-{day:02d}",
                aid,
                utype,
                beds,
                int(bua),
                finishing,
                "true" if furnished else "false",
                int(round(rent / 100.0) * 100),
            ]
        )
    return rows


# ---------------------------------------------------------------- orchestration

README_TEXT = """# SYNTHETIC DEMO DATA - NOT REAL

> **WARNING: every file in this folder is synthetic.** Areas are real Egyptian districts, but the
> developers, projects, units, prices, payment plans, price indices and rental listings are
> invented for demonstration. Nothing here is a real listing, a real price or investment advice.
> Developer names are fictional.

## Generation method

- Script: `scripts/generate_synthetic_data.py`. Seed: `{seed}`. Sizes: {units} units,
  {projects} projects, {listings} rental listings. Deterministic: same seed and options give
  byte-identical files (`manifest.json` lists row counts and sha256 per file).
- `macro_monthly.csv`: CPI YoY and EGP/USD are **interpolated** from the real World Bank annual
  averages in `demo_data/public/` (annual value at mid-year, linear interpolation; EGP/USD
  interpolated in log space; 2026 months move toward the two real monthly CPI points, and EGP/USD
  is held at the last annual value). These are NOT official monthly values. The CBE deposit and
  lending rates are a **synthetic step path** (changes only in months with a plausible MPC
  meeting, big hikes 2016-11, 2022-2023, 2024-03, cuts 2025-2026) anchored to end exactly at the
  real current rate (deposit 20.00, lending 21.00). Provenance column: `{prov}`.
- `area_price_index.csv`: monthly nominal EGP index per area (100 at 2015-01). Log drift =
  0.65-0.85 x inflation + area premium + seasonality + AR(1) noise, plus level jumps after
  the devaluations of 2016-11, 2022-03, 2022-10, 2023-01 and 2024-03. `avg_price_per_m2` =
  area base price 2015 x index / 100.
- `units.csv`: price = 2026-10 area price per m2 x developer tier x built-up area (plus 30% of
  garden) x type, finishing, floor and view multipliers x lognormal noise, rounded to 5,000 EGP.
- `rental_listings.csv`: monthly rent = value at listing date x gross yield (by area, type,
  furnished) / 12 x noise.
- `payment_plans.csv`: 1-3 plans per project; `cash_discount_pct` is the discount for paying
  cash instead of the plan.
- `projects.csv` `amenities` is a pipe-separated tag list.
"""


def generate(
    out: Path, public: Path, seed: int, units: int, projects: int, listings: int
) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    streams = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(8)]
    macro = build_macro(public)
    areas = build_areas()
    developers = build_developers(streams[1])
    proj = build_projects(streams[2], projects, developers)
    plans = build_payment_plans(streams[3], proj)
    index_rows, levels = build_area_index(streams[4], macro)
    unit_rows = build_units(streams[5], units, proj, developers, levels)
    rentals = build_rentals(streams[6], listings, areas, levels)

    tables: dict[str, tuple[Sequence[str], list[list[object]]]] = {
        "macro_monthly.csv": (
            [
                "month",
                "cpi_yoy_pct",
                "egp_per_usd",
                "cbe_deposit_rate",
                "cbe_lending_rate",
                "provenance",
            ],
            macro,
        ),
        "areas.csv": (
            [
                "id",
                "name_en",
                "name_ar",
                "type",
                "base_price_per_m2_2015",
                "liquidity_tier",
                "gross_rental_yield_base",
            ],
            areas,
        ),
        "developers.csv": (["id", "name_en", "tier", "on_time_delivery_rate"], developers),
        "projects.csv": (
            [
                "id",
                "name_en",
                "name_ar",
                "area_id",
                "developer_id",
                "launch_year",
                "delivery_year",
                "amenities",
            ],
            proj,
        ),
        "units.csv": (
            [
                "code",
                "project_id",
                "type",
                "bedrooms",
                "bua_m2",
                "garden_m2",
                "floor",
                "finishing",
                "delivery_year",
                "status",
                "price_egp",
                "view",
            ],
            unit_rows,
        ),
        "payment_plans.csv": (
            [
                "id",
                "project_id",
                "name",
                "down_payment_pct",
                "years",
                "frequency",
                "delivery_payment_pct",
                "maintenance_pct",
                "cash_discount_pct",
            ],
            plans,
        ),
        "area_price_index.csv": (
            ["month", "area_id", "index_level", "avg_price_per_m2"],
            index_rows,
        ),
        "rental_listings.csv": (
            [
                "id",
                "listing_date",
                "area_id",
                "type",
                "bedrooms",
                "bua_m2",
                "finishing",
                "furnished",
                "monthly_rent_egp",
            ],
            rentals,
        ),
    }
    files: dict[str, dict[str, object]] = {}
    for name, (header, rows) in tables.items():
        write_csv(out / name, header, rows)
        files[name] = {"rows": len(rows), "sha256": sha256(out / name)}
    manifest: dict[str, object] = {
        "synthetic": True,
        "seed": seed,
        "options": {"units": units, "projects": projects, "listings": listings},
        "files": files,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "README.md").write_text(
        README_TEXT.format(
            seed=seed, units=units, projects=projects, listings=listings, prov=MACRO_PROVENANCE
        ),
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--units", type=int, default=1500)
    parser.add_argument("--projects", type=int, default=40)
    parser.add_argument("--listings", type=int, default=5000)
    args = parser.parse_args(argv)
    manifest = generate(args.out, args.public, args.seed, args.units, args.projects, args.listings)
    files = manifest["files"]
    assert isinstance(files, dict)
    for name, info in files.items():
        print(f"{name:24s} {info['rows']:>6d} rows  sha256={str(info['sha256'])[:16]}")


if __name__ == "__main__":
    main()
