# SYNTHETIC DEMO DATA - NOT REAL

> **WARNING: every file in this folder is synthetic.** Areas are real Egyptian districts, but the
> developers, projects, units, prices, payment plans, price indices and rental listings are
> invented for demonstration. Nothing here is a real listing, a real price or investment advice.
> Developer names are fictional.

## Generation method

- Script: `scripts/generate_synthetic_data.py`. Seed: `20261109`. Sizes: 1500 units,
  40 projects, 5000 rental listings. Deterministic: same seed and options give
  byte-identical files (`manifest.json` lists row counts and sha256 per file).
- `macro_monthly.csv`: CPI YoY and EGP/USD are **interpolated** from the real World Bank annual
  averages in `demo_data/public/` (annual value at mid-year, linear interpolation; EGP/USD
  interpolated in log space; 2026 months move toward the two real monthly CPI points, and EGP/USD
  is held at the last annual value). These are NOT official monthly values. The CBE deposit and
  lending rates are a **synthetic step path** (changes only in months with a plausible MPC
  meeting, big hikes 2016-11, 2022-2023, 2024-03, cuts 2025-2026) anchored to end exactly at the
  real current rate (deposit 20.00, lending 21.00). Provenance column: `cpi_fx=interpolated_from_worldbank_annual;cbe=synthetic_anchored_to_current`.
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
