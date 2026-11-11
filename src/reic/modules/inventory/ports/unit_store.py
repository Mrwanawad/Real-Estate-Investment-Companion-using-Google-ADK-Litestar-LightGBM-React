from typing import Protocol

from reic.modules.inventory.domain.models import Area, UnitDetail, UnitQuery


class UnitStore(Protocol):
    async def search(self, query: UnitQuery, limit: int) -> list[UnitDetail]:
        """Units matching the filters, cheapest first. Payment fields of the query are ignored."""
        ...

    async def get_by_code(self, code: str) -> UnitDetail | None: ...

    async def list_areas(self) -> list[Area]: ...
