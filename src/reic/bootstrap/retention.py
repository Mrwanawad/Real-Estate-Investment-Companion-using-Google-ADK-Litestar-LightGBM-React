"""Data retention: chats and leads older than RETENTION_DAYS are deleted on startup."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)

_PURGE = (
    text("DELETE FROM chat_sessions WHERE updated_at < now() - make_interval(days => :days)"),
    text("DELETE FROM leads WHERE updated_at < now() - make_interval(days => :days)"),
)


async def purge_expired(session_factory: async_sessionmaker[AsyncSession], days: int) -> int:
    if days <= 0:
        return 0
    removed = 0
    try:
        async with session_factory() as session, session.begin():
            for statement in _PURGE:
                removed += (await session.execute(statement, {"days": days})).rowcount or 0
    except Exception:  # retention must never stop the API from starting
        log.exception("retention purge failed")
        return 0
    if removed:
        log.info("retention purge removed %d rows older than %d days", removed, days)
    return removed
