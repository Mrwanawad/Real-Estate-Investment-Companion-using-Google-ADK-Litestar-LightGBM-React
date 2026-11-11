from litestar.testing import TestClient

from reic.bootstrap.app import create_app
from reic.shared.config import Settings


def test_session_creation_is_limited_per_client() -> None:
    with TestClient(app=create_app(Settings(rate_limit_per_minute=2))) as client:
        codes = [client.post("/chat/sessions", json={}).status_code for _ in range(3)]
        health = [client.get("/health").status_code for _ in range(3)]
    assert codes == [201, 201, 429]
    assert health == [200, 200, 200]


def test_proxy_header_separates_clients() -> None:
    settings = Settings(rate_limit_per_minute=1, client_ip_header="Fly-Client-IP")
    with TestClient(app=create_app(settings)) as client:
        first = client.post("/chat/sessions", json={}, headers={"Fly-Client-IP": "1.1.1.1"})
        again = client.post("/chat/sessions", json={}, headers={"Fly-Client-IP": "1.1.1.1"})
        other = client.post("/chat/sessions", json={}, headers={"Fly-Client-IP": "2.2.2.2"})
    assert (first.status_code, again.status_code, other.status_code) == (201, 429, 201)


def test_zero_disables_the_limit() -> None:
    with TestClient(app=create_app(Settings(rate_limit_per_minute=0))) as client:
        codes = {client.post("/chat/sessions", json={}).status_code for _ in range(5)}
    assert codes == {201}
