from collections.abc import Sequence

from reic.modules.inventory.domain.areas import AreaResolver
from reic.modules.inventory.domain.errors import UnitNotFoundError, UnknownAreaError
from reic.modules.inventory.domain.models import Area, Goal, UnitDetail, UnitQuery
from reic.modules.inventory.domain.scoring import ScoredUnit, ShortlistScorer
from reic.modules.inventory.ports.unit_store import UnitStore

CANDIDATE_CAP = 1000


async def _with_resolved_areas(
    store: UnitStore, query: UnitQuery, areas: Sequence[str]
) -> UnitQuery:
    if not areas:
        return query
    resolver = AreaResolver(await store.list_areas())
    ids = list(query.area_ids)
    for name in areas:
        area_id = resolver.resolve(name)
        if area_id is None:
            raise UnknownAreaError(name)
        if area_id not in ids:
            ids.append(area_id)
    return query.model_copy(update={"area_ids": tuple(ids)})


class SearchUnits:
    def __init__(self, store: UnitStore) -> None:
        self._store = store

    async def execute(
        self, query: UnitQuery, *, areas: Sequence[str] = (), limit: int = 50
    ) -> list[UnitDetail]:
        """`areas` may hold ids, English or Arabic names, or aliases; they add to query.area_ids."""
        resolved = await _with_resolved_areas(self._store, query, areas)
        return await self._store.search(resolved, limit)


class GetUnit:
    def __init__(self, store: UnitStore) -> None:
        self._store = store

    async def execute(self, code: str) -> UnitDetail:
        detail = await self._store.get_by_code(code)
        if detail is None:
            raise UnitNotFoundError(code)
        return detail


class ListAreas:
    def __init__(self, store: UnitStore) -> None:
        self._store = store

    async def execute(self) -> list[Area]:
        return await self._store.list_areas()


class BuildShortlist:
    def __init__(self, store: UnitStore, scorer: ShortlistScorer | None = None) -> None:
        self._store = store
        self._scorer = scorer or ShortlistScorer()

    async def execute(
        self, query: UnitQuery, goal: Goal, *, areas: Sequence[str] = (), limit: int = 5
    ) -> list[ScoredUnit]:
        resolved = await _with_resolved_areas(self._store, query, areas)
        candidates = await self._store.search(resolved, CANDIDATE_CAP)
        return self._scorer.rank(candidates, resolved, goal)[:limit]
