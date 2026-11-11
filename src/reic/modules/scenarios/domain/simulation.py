"""Monte Carlo of a property purchase over annual steps.

Conventions:
- Price growth per year is log-normal with arithmetic mean `annual_growth_mean`; with zero vol it
  is exactly (1 + mean) per year.
- Inflation is normal per year (floored at -50%) and drives rent growth and the real deflator.
- Rent in year t (1-based) = price * gross_yield * inflation index at t-1, earned only when
  t > years_to_delivery, reduced by vacancy (beta, mean `vacancy_mean`) and maintenance.
- Cash flows: -cost at t=0, net rent each year, net sale proceeds at the horizon.
  cost = price * (1 + upfront_cost_pct).
All rates are fractions; reported return fields ending in _pct are in percent.
"""

from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np

QUANTILES = (10, 50, 90)
VACANCY_CONCENTRATION = 20.0  # beta a+b: higher means vacancy draws stay closer to the mean


@dataclass(frozen=True)
class SimulationParams:
    price_egp: float
    horizon_years: int
    annual_growth_mean: float
    annual_growth_vol: float
    gross_yield: float = 0.0
    upfront_cost_pct: float = 0.03
    exit_cost_pct: float = 0.025
    vacancy_mean: float = 0.10
    maintenance_pct: float = 0.10
    inflation_mean: float = 0.15
    inflation_vol: float = 0.05
    goal: str = "resell"
    years_to_delivery: int = 0
    n_paths: int = 5000
    seed: int = 42


def _q(values: np.ndarray, scale: float = 1.0) -> dict[str, float]:
    p10, p50, p90 = np.percentile(values, QUANTILES) * scale
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90)}


def _irr(flows: np.ndarray) -> np.ndarray:
    """Per-path IRR by bisection. flows: (paths, T+1), one outflow first then inflows, so NPV
    falls monotonically in the rate. Bounded to [-99%, 500%]."""
    lo = np.full(flows.shape[0], -0.99)
    hi = np.full(flows.shape[0], 5.0)
    t = np.arange(flows.shape[1])
    for _ in range(80):
        mid = (lo + hi) / 2
        npv = (flows / (1 + mid)[:, None] ** t).sum(axis=1)
        positive = npv > 0
        lo = np.where(positive, mid, lo)
        hi = np.where(positive, hi, mid)
    return (lo + hi) / 2


def _run(p: SimulationParams) -> dict[str, Any]:
    rng = np.random.default_rng(p.seed)
    n, years = p.n_paths, p.horizon_years
    cost = p.price_egp * (1 + p.upfront_cost_pct)

    mean_factor = 1 + p.annual_growth_mean
    sigma = np.sqrt(np.log1p((p.annual_growth_vol / mean_factor) ** 2))
    growth = np.exp(np.log(mean_factor) - sigma**2 / 2 + sigma * rng.standard_normal((n, years)))
    inflation = np.maximum(
        p.inflation_mean + p.inflation_vol * rng.standard_normal((n, years)), -0.5
    )
    if 0 < p.vacancy_mean < 1:
        a = p.vacancy_mean * VACANCY_CONCENTRATION
        vacancy = rng.beta(a, VACANCY_CONCENTRATION - a, size=(n, years))
    else:
        vacancy = np.full((n, years), float(np.clip(p.vacancy_mean, 0, 1)))

    value = p.price_egp * np.cumprod(growth, axis=1)  # years 1..T
    infl_index = np.cumprod(1 + inflation, axis=1)  # index at end of year t
    infl_before = np.concatenate([np.ones((n, 1)), infl_index[:, :-1]], axis=1)
    year_no = np.arange(1, years + 1)
    earning = (year_no > p.years_to_delivery).astype(float)
    net_rent = (
        p.price_egp
        * p.gross_yield
        * infl_before
        * (1 - vacancy)
        * (1 - p.maintenance_pct)
        * earning
    )
    cum_rent = np.cumsum(net_rent, axis=1)

    exit_value = value[:, -1] * (1 - p.exit_cost_pct)
    wealth = exit_value + cum_rent[:, -1]
    total_return = wealth / cost - 1
    real_return = wealth / infl_index[:, -1] / cost - 1

    flows = np.concatenate([np.full((n, 1), -cost), net_rent], axis=1)
    flows[:, -1] += exit_value

    cum_wealth_p50 = np.median(value * (1 - p.exit_cost_pct) + cum_rent, axis=0)
    reached = np.nonzero(cum_wealth_p50 >= cost)[0]

    path_years = np.concatenate([np.full((n, 1), p.price_egp), value], axis=1)
    p10, p50, p90 = np.percentile(path_years, QUANTILES, axis=0)
    return {
        "value_at_horizon": _q(value[:, -1]),
        "value_path": [
            {"year": y, "p10": float(p10[y]), "p50": float(p50[y]), "p90": float(p90[y])}
            for y in range(years + 1)
        ],
        "net_rent_total": _q(cum_rent[:, -1]),
        "total_return_pct": _q(total_return, 100),
        "irr": _q(_irr(flows)),
        "real_return_pct": float(np.median(real_return) * 100),
        "prob_loss": float((total_return < 0).mean()),
        "prob_real_loss": float((real_return < 0).mean()),
        "break_even_year": int(reached[0]) + 1 if reached.size else None,
    }


def _sensitivity(p: SimulationParams) -> list[dict[str, Any]]:
    def p50(**changes: Any) -> float:
        return _run(replace(p, **changes))["total_return_pct"]["p50"]

    cases = [
        (
            "annual_growth",
            {"annual_growth_mean": p.annual_growth_mean - p.annual_growth_vol},
            {"annual_growth_mean": p.annual_growth_mean + p.annual_growth_vol},
        ),
        (
            "gross_yield",
            {"gross_yield": p.gross_yield * 0.8},
            {"gross_yield": p.gross_yield * 1.2},
        ),
        ("vacancy", {"vacancy_mean": 0.25}, {"vacancy_mean": 0.05}),
        ("exit_cost", {"exit_cost_pct": 0.05}, {"exit_cost_pct": 0.01}),
    ]
    return [{"driver": name, "low": p50(**lo), "high": p50(**hi)} for name, lo, hi in cases]


def simulate(params: SimulationParams) -> dict[str, Any]:
    """Run the Monte Carlo. Sensitivity `low`/`high` are the P50 total return (%) with each
    driver set unfavourably / favourably (same seed, so draws are common across cases)."""
    result = _run(params)
    result["sensitivity"] = _sensitivity(params)
    result["assumptions"] = asdict(params)
    return result
