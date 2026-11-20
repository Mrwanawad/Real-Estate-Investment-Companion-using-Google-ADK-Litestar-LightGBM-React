from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from reic.modules.companion.adapters.outbound.sql_session_store import SqlSessionStore
from reic.shared.db import create_engine, create_session_factory
from tests.integration.conftest import PostgresUrls

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated(postgres: PostgresUrls) -> Iterator[PostgresUrls]:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres.asynchronous.replace("%", "%%"))
    command.upgrade(config, "head")
    yield postgres


@pytest.fixture
async def engine(migrated: PostgresUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(migrated.asynchronous)
    yield engine
    await engine.dispose()


async def test_save_load_and_overwrite_session(engine: AsyncEngine) -> None:
    store = SqlSessionStore(create_session_factory(engine))
    assert await store.load("nope") is None
    doc = {
        "language": "ar",
        "profile": {"budget_egp": 5_000_000, "areas": ["مدينتي"]},
        "artifacts": {"financing": {"price_egp": Decimal("4800000.00")}},
        "messages": [{"role": "user", "text": "معايا ٥ مليون"}],
        "results": [],
        "lead_id": None,
    }
    await store.save("s1", doc)
    loaded = await store.load("s1")
    assert loaded is not None
    assert loaded["artifacts"]["financing"]["price_egp"] == "4800000.00"
    assert loaded["profile"]["areas"] == ["مدينتي"]

    await store.save("s1", {**doc, "lead_id": "lead-9"})
    again = await store.load("s1")
    assert again is not None and again["lead_id"] == "lead-9"


async def test_retention_purges_old_chats_and_sessions_can_be_deleted(engine: AsyncEngine) -> None:
    from sqlalchemy import text

    from reic.bootstrap.retention import purge_expired

    factory = create_session_factory(engine)
    store = SqlSessionStore(factory)
    await store.save("old", {"language": "en"})
    await store.save("fresh", {"language": "en"})
    await store.save("gone", {"language": "en"})
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE chat_sessions SET updated_at = now() - interval '91 days' WHERE id = 'old'"
            )
        )
    assert await purge_expired(factory, 90) >= 1
    await store.delete("gone")
    assert await store.load("old") is None and await store.load("gone") is None
    assert await store.load("fresh") is not None


async def test_broker_directory_counts_open_leads(engine: AsyncEngine) -> None:
    from sqlalchemy import text

    from reic.modules.handoff.adapters.outbound.notifiers import NullNotifier
    from reic.modules.handoff.adapters.outbound.sql_broker_directory import SqlBrokerDirectory
    from reic.modules.handoff.adapters.outbound.sql_lead_store import SqlLeadStore
    from reic.modules.handoff.application.service import HandoffService

    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await session.execute(text("DELETE FROM brokers"))
        await session.execute(
            text(
                "INSERT INTO brokers (id, name, phone, email, languages, area_ids) VALUES "
                "('B1', 'A', '+20', 'a@x.example', '[\"ar\"]', '[\"Madinaty\", \"مدينتي\"]')"
            )
        )
    directory = SqlBrokerDirectory(factory)
    service = HandoffService(SqlLeadStore(factory), NullNotifier(), directory)
    created = await service.create_lead(
        {"phone": "01000000000", "language": "ar", "summary": "x", "profile": {"areas": ["مدينتي"]}}
    )
    assert created["broker"]["id"] == "B1"
    assert (await directory.open_leads())["B1"] >= 1
