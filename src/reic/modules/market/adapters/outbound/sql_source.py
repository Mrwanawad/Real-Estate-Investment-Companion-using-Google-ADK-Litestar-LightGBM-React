from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.market.adapters.outbound.rows import build_market_data
from reic.modules.market.domain.models import MarketData

# Raw SQL keeps this module independent of the inventory module's table definitions.
# Tables come from migration 0002.
_INDEX_SQL = text("SELECT month, area_id, index_level FROM area_price_index")
_UNITS_SQL = text(
    """
    SELECT u.type, u.bedrooms, u.bua_m2, u.garden_m2, u.floor, u.finishing, u.delivery_year,
           u.price_egp, p.area_id, d.tier AS developer_tier
    FROM units u
    JOIN projects p ON p.id = u.project_id
    JOIN developers d ON d.id = p.developer_id
    """
)
_RENTALS_SQL = text(
    """
    SELECT listing_date, area_id, type, bedrooms, bua_m2, finishing, furnished, monthly_rent_egp
    FROM rental_listings
    """
)


class SqlMarketDataSource:
    """MarketDataSource over Postgres. Opens one short session per load."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load(self) -> MarketData:
        async with self._session_factory() as session:
            index = (await session.execute(_INDEX_SQL)).mappings().all()
            units = (await session.execute(_UNITS_SQL)).mappings().all()
            rentals = (await session.execute(_RENTALS_SQL)).mappings().all()
        return build_market_data(index, units, rentals)
