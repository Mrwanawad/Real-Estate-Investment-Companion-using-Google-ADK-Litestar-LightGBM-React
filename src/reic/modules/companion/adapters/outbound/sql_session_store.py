"""Chat sessions in Postgres (one JSONB document per session). Table from migration 0004."""

import json
from typing import Any

from sqlalchemy import Column, DateTime, MetaData, String, Table, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

metadata = MetaData()

chat_sessions = Table(
    "chat_sessions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("language", String(8), nullable=False, server_default="en"),
    Column("data", JSONB, nullable=False),
)


class SqlSessionStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def load(self, session_id: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(chat_sessions.c.data).where(chat_sessions.c.id == session_id)
            )
        return dict(row) if row is not None else None

    async def save(self, session_id: str, data: dict[str, Any]) -> None:
        # Tool results carry Decimals; store them as the strings the client already sees.
        doc = json.loads(json.dumps(data, ensure_ascii=False, default=str))
        stmt = insert(chat_sessions).values(
            id=session_id, language=doc.get("language", "en"), data=doc
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[chat_sessions.c.id],
            set_={
                "data": stmt.excluded.data,
                "language": stmt.excluded.language,
                "updated_at": func.now(),
            },
        )
        async with self._sessions() as session, session.begin():
            await session.execute(stmt)

    async def delete(self, session_id: str) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(delete(chat_sessions).where(chat_sessions.c.id == session_id))
