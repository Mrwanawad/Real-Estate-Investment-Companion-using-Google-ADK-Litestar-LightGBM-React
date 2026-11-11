from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reic.modules.handoff.adapters.outbound.tables import leads
from reic.modules.handoff.domain.models import Lead


def _lead(row: Row[Any]) -> Lead:
    return Lead(**row._mapping)


class SqlLeadStore:
    """LeadStore over SQLAlchemy async; opens one short session per call."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def add(self, lead: Lead) -> None:
        async with self._factory() as session, session.begin():
            await session.execute(insert(leads).values(**lead.__dict__))

    async def get(self, lead_id: str) -> Lead | None:
        async with self._factory() as session:
            row = (await session.execute(select(leads).where(leads.c.id == lead_id))).first()
        return _lead(row) if row else None

    async def list(self, status: str | None, limit: int) -> list[Lead]:
        query = select(leads).order_by(leads.c.created_at.desc()).limit(limit)
        if status is not None:
            query = query.where(leads.c.status == status)
        async with self._factory() as session:
            rows = (await session.execute(query)).all()
        return [_lead(r) for r in rows]

    async def save_status(self, lead: Lead, expected_status: str) -> bool:
        async with self._factory() as session, session.begin():
            result = await session.execute(
                update(leads)
                .where(leads.c.id == lead.id, leads.c.status == expected_status)
                .values(status=lead.status, updated_at=lead.updated_at)
            )
        return bool(result.rowcount)
