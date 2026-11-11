import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


@dataclass(frozen=True)
class PostgresUrls:
    sync: str
    asynchronous: str


def _embedded_postgres(path: Path) -> Iterator[str]:
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(path)
    try:
        yield server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    finally:
        server.cleanup()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in Path(str(item.fspath)).parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[PostgresUrls]:
    """Uses TEST_DATABASE_URL when set, otherwise an embedded Postgres with pgvector.

    TEST_DATABASE_URL may use any postgresql driver prefix; it is normalised to psycopg (sync)
    and asyncpg (async). The embedded data directory lives under the system temp dir, outside
    the spaced project path.
    """
    external = os.environ.get("TEST_DATABASE_URL")
    urls = iter([external]) if external else _embedded_postgres(tmp_path_factory.mktemp("pg"))
    raw = next(urls)
    base = raw.split("://", 1)[1]
    sync_url = f"postgresql+psycopg://{base}"
    engine = create_engine(sync_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine.dispose()
    yield PostgresUrls(sync_url, f"postgresql+asyncpg://{base}")
    next(urls, None)
