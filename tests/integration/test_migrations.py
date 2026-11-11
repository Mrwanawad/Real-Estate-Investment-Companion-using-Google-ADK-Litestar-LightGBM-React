from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.integration.conftest import PostgresUrls

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _extension_count(sync_url: str) -> int:
    engine = create_engine(sync_url)
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
    engine.dispose()
    return count


def test_upgrade_head_then_downgrade_base(postgres: PostgresUrls) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres.asynchronous.replace("%", "%%"))

    command.upgrade(config, "head")
    assert _extension_count(postgres.sync) == 1

    command.downgrade(config, "base")
    assert _extension_count(postgres.sync) == 0

    # Leave the extension in place for other integration tests in the session.
    command.upgrade(config, "head")
