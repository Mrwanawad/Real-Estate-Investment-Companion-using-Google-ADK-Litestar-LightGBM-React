from litestar import Controller, get, post
from litestar.exceptions import NotFoundException, ValidationException

from reic.modules.inventory.adapters.inbound.schemas import (
    AreaOut,
    SearchRequest,
    ShortlistItemOut,
    ShortlistRequest,
    UnitOut,
)
from reic.modules.inventory.application.use_cases import (
    BuildShortlist,
    GetUnit,
    ListAreas,
    SearchUnits,
)
from reic.modules.inventory.domain.errors import UnitNotFoundError, UnknownAreaError
from reic.modules.inventory.domain.models import UnitQuery


def _query(data: SearchRequest) -> UnitQuery:
    return UnitQuery(**data.model_dump(exclude={"areas", "limit", "goal"}))


class InventoryController(Controller):
    """Use cases (search_units, build_shortlist, get_unit, list_areas) are injected by bootstrap."""

    path = "/inventory"

    @post("/search", status_code=200)
    async def search(self, data: SearchRequest, search_units: SearchUnits) -> list[UnitOut]:
        try:
            details = await search_units.execute(_query(data), areas=data.areas, limit=data.limit)
        except UnknownAreaError as exc:
            raise ValidationException(str(exc)) from exc
        return [UnitOut.from_domain(d) for d in details]

    @post("/shortlist", status_code=200)
    async def shortlist(
        self, data: ShortlistRequest, build_shortlist: BuildShortlist
    ) -> list[ShortlistItemOut]:
        try:
            scored = await build_shortlist.execute(
                _query(data), data.goal, areas=data.areas, limit=data.limit
            )
        except UnknownAreaError as exc:
            raise ValidationException(str(exc)) from exc
        return [ShortlistItemOut.from_domain(s) for s in scored]

    @get("/units/{code:str}")
    async def get_unit(self, code: str, get_unit: GetUnit) -> UnitOut:
        try:
            return UnitOut.from_domain(await get_unit.execute(code))
        except UnitNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc

    @get("/areas")
    async def areas(self, list_areas: ListAreas) -> list[AreaOut]:
        return [AreaOut.from_domain(a) for a in await list_areas.execute()]
