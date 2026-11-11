import numpy as np
import pytest
from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, text

from tests.integration.conftest import PostgresUrls

pytestmark = pytest.mark.integration


def test_vector_extension_and_roundtrip(postgres: PostgresUrls) -> None:
    engine = create_engine(postgres.sync)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        installed = connection.execute(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
        assert installed == 1
        connection.execute(text("CREATE TEMP TABLE items (id int, embedding vector(3))"))
        connection.execute(text("INSERT INTO items VALUES (1, '[1,2,3]'), (2, '[4,5,6]')"))
        nearest = connection.execute(
            text("SELECT id FROM items ORDER BY embedding <-> '[1,2,4]' LIMIT 1")
        ).scalar_one()
        assert nearest == 1
        raw = connection.connection.dbapi_connection
        register_vector(raw)
        row = raw.execute("SELECT embedding FROM items WHERE id = 2").fetchone()
        assert np.allclose(row[0].to_numpy(), [4.0, 5.0, 6.0])
    engine.dispose()
