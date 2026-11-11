from litestar.testing import TestClient

from reic import __version__
from reic.bootstrap.app import create_app
from reic.shared.config import Settings


def test_health_returns_ok_and_version() -> None:
    with TestClient(app=create_app(Settings())) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_cors_allows_configured_origin() -> None:
    settings = Settings(cors_origins=["http://example.test"])
    with TestClient(app=create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "http://example.test"})
    assert response.headers["access-control-allow-origin"] == "http://example.test"
