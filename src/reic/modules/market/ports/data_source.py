from typing import Protocol

from reic.modules.market.domain.models import MarketData


class MarketDataSource(Protocol):
    async def load(self) -> MarketData:
        """All training data: area indices, priced units and rental listings."""
        ...
