import asyncio
import csv
from pathlib import Path

from reic.modules.market.adapters.outbound.rows import Row, build_market_data
from reic.modules.market.domain.models import MarketData


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class CsvMarketDataSource:
    """MarketDataSource over the synthetic CSVs (demo_data/synthetic). Used by tests and scripts."""

    def __init__(self, directory: Path, inventory_dir: Path | None = None) -> None:
        self._dir = directory
        self._inventory = inventory_dir or directory  # units, projects, developers

    def load_sync(self) -> MarketData:
        projects = {p["id"]: p for p in _read(self._inventory / "projects.csv")}
        tiers = {d["id"]: d["tier"] for d in _read(self._inventory / "developers.csv")}
        units: list[Row] = []
        for u in _read(self._inventory / "units.csv"):
            project = projects[u["project_id"]]
            units.append(
                {
                    **u,
                    "area_id": project["area_id"],
                    "developer_tier": tiers[project["developer_id"]],
                }
            )
        return build_market_data(
            _read(self._dir / "area_price_index.csv"),
            units,
            _read(self._dir / "rental_listings.csv"),
        )

    async def load(self) -> MarketData:
        return await asyncio.to_thread(self.load_sync)
