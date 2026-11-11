class MarketError(Exception):
    """Base class for market domain errors."""


class UnknownAreaError(MarketError):
    def __init__(self, area_id: str) -> None:
        super().__init__(f"Unknown area: {area_id!r}")
        self.area_id = area_id


class InvalidInputError(MarketError):
    """Input that cannot be priced (bad horizon, bad unit fields)."""
