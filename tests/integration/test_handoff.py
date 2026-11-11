from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from reic.modules.handoff.adapters.outbound.notifiers import NullNotifier
from reic.modules.handoff.adapters.outbound.sql_lead_store import SqlLeadStore
from reic.modules.handoff.application.service import HandoffService
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


async def test_create_list_update_lead(engine: AsyncEngine) -> None:
    service = HandoffService(SqlLeadStore(create_session_factory(engine)), NullNotifier())
    created = await service.create_lead(
        {
            "email": "buyer@example.com",
            "language": "ar",
            "goal": "live",
            "budget_egp": 3_500_000,
            "profile": {"bedrooms": 3, "areas": ["new-cairo"]},
            "summary": "Family wants a 3BR to live in.",
            "unit_codes": ["U-1", "U-2"],
            "session_id": "sess-1",
        }
    )
    assert created["status"] == "new"

    listed = await service.list_leads("new", 50)
    mine = next(x for x in listed if x["id"] == created["lead_id"])
    assert mine["profile"]["bedrooms"] == 3
    assert mine["unit_codes"] == ["U-1", "U-2"]
    assert mine["budget_egp"] == 3_500_000

    updated = await service.update_status(created["lead_id"], "contacted")
    assert updated["status"] == "contacted"
    assert updated["updated_at"] >= mine["updated_at"]
    assert all(x["id"] != created["lead_id"] for x in await service.list_leads("new", 50))
    assert any(x["id"] == created["lead_id"] for x in await service.list_leads("contacted", 50))


async def test_stale_status_write_is_rejected(engine: AsyncEngine) -> None:
    store = SqlLeadStore(create_session_factory(engine))
    service = HandoffService(store, NullNotifier())
    created = await service.create_lead({"phone": "+20100", "summary": "s", "profile": {}})
    stale = await store.get(created["lead_id"])
    assert stale is not None
    await service.update_status(created["lead_id"], "closed")
    stale.move_to("contacted")
    assert await store.save_status(stale, "new") is False
    current = await store.get(created["lead_id"])
    assert current is not None
    assert current.status == "closed"
