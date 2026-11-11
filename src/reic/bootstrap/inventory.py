"""Wiring for the inventory module: session, store and use-case dependencies plus the router."""

from collections.abc import AsyncIterator

from litestar import Router
from litestar.di import Provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.inventory.adapters.inbound.controller import InventoryController
from reic.modules.inventory.adapters.outbound.sql_unit_store import SqlUnitStore
from reic.modules.inventory.application.use_cases import (
    BuildShortlist,
    GetUnit,
    ListAreas,
    SearchUnits,
)


def build_inventory_router(session_factory: async_sessionmaker[AsyncSession]) -> Router:
    async def provide_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def provide_store(session: AsyncSession) -> SqlUnitStore:
        return SqlUnitStore(session)

    def provide_search(store: SqlUnitStore) -> SearchUnits:
        return SearchUnits(store)

    def provide_shortlist(store: SqlUnitStore) -> BuildShortlist:
        return BuildShortlist(store)

    def provide_get_unit(store: SqlUnitStore) -> GetUnit:
        return GetUnit(store)

    def provide_list_areas(store: SqlUnitStore) -> ListAreas:
        return ListAreas(store)

    return Router(
        path="/",
        route_handlers=[InventoryController],
        dependencies={
            "session": Provide(provide_session),
            "store": Provide(provide_store, sync_to_thread=False),
            "search_units": Provide(provide_search, sync_to_thread=False),
            "build_shortlist": Provide(provide_shortlist, sync_to_thread=False),
            "get_unit": Provide(provide_get_unit, sync_to_thread=False),
            "list_areas": Provide(provide_list_areas, sync_to_thread=False),
        },
    )
