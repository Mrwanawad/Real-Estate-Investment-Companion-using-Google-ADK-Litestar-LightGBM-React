class InventoryError(Exception):
    """Base class for inventory domain errors."""


class UnknownAreaError(InventoryError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown area: {name!r}")
        self.name = name


class UnitNotFoundError(InventoryError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Unit not found: {code!r}")
        self.code = code
