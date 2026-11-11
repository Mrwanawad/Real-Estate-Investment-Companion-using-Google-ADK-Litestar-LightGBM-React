# Public indices (real data, retrieved 2026-11-09)

Everything in this folder was fetched from public sources. Each row carries its `source_url` and `retrieved_at`.

| File | What it is | Source |
|---|---|---|
| `cpi_inflation_annual_worldbank.csv` | Egypt CPI inflation, annual average %, 2015-2025 (World Bank indicator `FP.CPI.TOTL.ZG`) | https://api.worldbank.org/v2/country/EGY/indicator/FP.CPI.TOTL.ZG?format=json&per_page=100 |
| `egp_usd_annual_worldbank.csv` | Official EGP per USD, annual average, 2015-2025 (World Bank indicator `PA.NUS.FCRF`) | https://api.worldbank.org/v2/country/EGY/indicator/PA.NUS.FCRF?format=json&per_page=100 |
| `cbe_rates.csv` | Central Bank of Egypt overnight deposit / lending rate: 1 row, decision date 2026-10-29, deposit 20.00%, lending 21.00% | https://www.cbe.org.eg/en/economic-research/statistics/overnight-deposit-and-lending-rate |
| `cpi_inflation.csv` | Urban headline inflation YoY: 2 monthly points, 2026-09 = 13.90%, 2026-10 = 12.70% | https://tradingeconomics.com/egypt/inflation-cpi |

## What could not be fetched

- Monthly CBE rate history (only the current rate was retrievable).
- Monthly CPI history and monthly EGP/USD (only the annual World Bank series and the two recent CPI points above).

The synthetic dataset (`../synthetic/macro_monthly.csv`) fills these gaps by interpolation and clearly labels
its provenance. Those monthly values are NOT official statistics.
