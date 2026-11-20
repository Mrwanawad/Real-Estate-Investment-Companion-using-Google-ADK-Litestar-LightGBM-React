"""Litestar Store over Postgres, so rate-limit counters are shared by every API instance.

Serverless hosts run several instances at once; an in-memory store would let each one count
its own limit. Table from migration 0006.
"""

from datetime import UTC, datetime, timedelta

from litestar.stores.base import Store
from sqlalchemy import (
    Column,
    DateTime,
    LargeBinary,
    MetaData,
    Table,
    Text,
    delete,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

kv_store = Table(
    "kv_store",
    MetaData(),
    Column("key", Text, primary_key=True),
    Column("value", LargeBinary, nullable=False),
    Column("expires_at", DateTime(timezone=True)),
)


def _seconds(value: int | timedelta | None) -> float | None:
    if value is None:
        return None
    return value.total_seconds() if isinstance(value, timedelta) else float(value)


def _alive():  # type: ignore[no-untyped-def]
    return or_(kv_store.c.expires_at.is_(None), kv_store.c.expires_at > func.now())


class PostgresStore(Store):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def set(
        self, key: str, value: str | bytes, expires_in: int | timedelta | None = None
    ) -> None:
        data = value.encode() if isinstance(value, str) else value
        seconds = _seconds(expires_in)
        expires_at = datetime.now(UTC) + timedelta(seconds=seconds) if seconds else None
        stmt = insert(kv_store).values(key=key, value=data, expires_at=expires_at)
        stmt = stmt.on_conflict_do_update(
            index_elements=[kv_store.c.key],
            set_={"value": stmt.excluded.value, "expires_at": stmt.excluded.expires_at},
        )
        async with self._factory() as session, session.begin():
            await session.execute(stmt)

    async def get(self, key: str, renew_for: int | timedelta | None = None) -> bytes | None:
        async with self._factory() as session:
            value = await session.scalar(
                select(kv_store.c.value).where(kv_store.c.key == key, _alive())
            )
        if value is not None and renew_for is not None:
            await self.set(key, value, renew_for)
        return bytes(value) if value is not None else None

    async def delete(self, key: str) -> None:
        async with self._factory() as session, session.begin():
            await session.execute(delete(kv_store).where(kv_store.c.key == key))

    async def delete_all(self) -> None:
        async with self._factory() as session, session.begin():
            await session.execute(delete(kv_store))

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def expires_in(self, key: str) -> int | None:
        async with self._factory() as session:
            expires_at = await session.scalar(
                select(kv_store.c.expires_at).where(kv_store.c.key == key, _alive())
            )
        if expires_at is None:
            return None
        return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
