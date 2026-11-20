from sqlalchemy import Boolean, Column, MetaData, String, Table, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.handoff.adapters.outbound.tables import leads
from reic.modules.handoff.domain.brokers import Broker

# Must stay in sync with migration 0005.
brokers = Table(
    "brokers",
    MetaData(),
    Column("id", String(16), primary_key=True),
    Column("name", Text, nullable=False),
    Column("phone", Text, nullable=False),
    Column("email", Text, nullable=False),
    Column("languages", JSONB, nullable=False),
    Column("area_ids", JSONB, nullable=False),  # holds area names (EN and AR)
    Column("simulated", Boolean, nullable=False),
)


class SqlBrokerDirectory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def brokers(self) -> list[Broker]:
        async with self._factory() as session:
            rows = (await session.execute(select(brokers).order_by(brokers.c.id))).all()
        return [
            Broker(
                id=r.id,
                name=r.name,
                phone=r.phone,
                email=r.email,
                languages=tuple(r.languages),
                areas=tuple(r.area_ids),
                simulated=r.simulated,
            )
            for r in rows
        ]

    async def open_leads(self) -> dict[str, int]:
        query = (
            select(leads.c.broker_id, func.count())
            .where(leads.c.broker_id.is_not(None), leads.c.status != "closed")
            .group_by(leads.c.broker_id)
        )
        async with self._factory() as session:
            rows = (await session.execute(query)).all()
        return {broker_id: count for broker_id, count in rows}
