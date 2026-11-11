"""Train the market models on the synthetic CSVs, run backtests and holdouts, record metrics.

Usage: .venv/Scripts/python scripts/train_market_models.py
Writes evals/results/market_metrics.json. Numbers come from synthetic demo data, not real prices.
"""

import asyncio
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

from reic.bootstrap.market import SYNTHETIC_DIR, build_csv_market_service
from reic.modules.market.adapters.outbound.csv_source import CsvMarketDataSource
from reic.modules.market.adapters.outbound.forecasters import SeasonalNaiveForecaster
from reic.modules.market.application.backtest import rolling_origin_backtest

OUT = Path(__file__).resolve().parents[1] / "evals" / "results" / "market_metrics.json"


async def main() -> None:
    started = time.perf_counter()
    service = build_csv_market_service()
    evaluation = await service.evaluation()
    seconds = time.perf_counter() - started

    data = CsvMarketDataSource(SYNTHETIC_DIR).load_sync()
    naive = [
        rolling_origin_backtest(SeasonalNaiveForecaster(), s.levels) for s in data.index.values()
    ]
    keys = ("mape", "mase", "coverage_80", "pinball")
    evaluation["forecast"]["baseline_seasonal_naive_mean_over_areas"] = {
        k: round(sum(getattr(b, k) for b in naive) / len(naive), 4) for k in keys
    }
    evaluation["meta"] = {
        "data": "synthetic demo data (demo_data/synthetic), NOT real prices",
        "backtest": "rolling origin, 3 non-overlapping origins x 12-month horizon per area",
        "holdout": "random 20% split, seed 7",
        "train_and_eval_seconds": round(seconds, 2),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")

    f, u, r = evaluation["forecast"], evaluation["unit_value"], evaluation["rent"]
    print(f"forecast {f['model']}: {f['mean_over_areas']}")
    print(f"forecast seasonal_naive: {f['baseline_seasonal_naive_mean_over_areas']}")
    print(
        f"unit value: served={u['served']} promoted={u['promoted']} "
        f"MAE model={u['holdout_mae_model']} baseline={u['holdout_mae_baseline']} EGP/m2 "
        f"P10-P90 coverage={u['holdout_coverage_80_model']}"
    )
    print(f"rent: MAE={r['holdout_mae']} EGP MAPE={r['holdout_mape']}")
    print(f"train+eval {seconds:.1f}s -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
