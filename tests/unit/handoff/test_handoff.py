import hashlib
import hmac
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from litestar import Litestar
from litestar.testing import TestClient
from pydantic import SecretStr

from reic.bootstrap.handoff import build_handoff_router, build_handoff_service
from reic.modules.handoff.adapters.outbound.notifiers import (
    HmacWebhookNotifier,
    NullNotifier,
    sign,
)
from reic.modules.handoff.application.service import HandoffService
from reic.modules.handoff.domain.errors import (
    InvalidStatusTransitionError,
    LeadNotFoundError,
    LeadValidationError,
)
from reic.modules.handoff.domain.models import Lead
from reic.shared.config import Settings

LEAD: dict[str, Any] = {
    "name": "Sara",
    "phone": "+201000000000",
    "language": "ar",
    "goal": "rent",
    "budget_egp": 4_000_000,
    "profile": {"bedrooms": 2},
    "summary": "Wants a 2BR to rent out in New Cairo.",
    "unit_codes": ["U-1"],
}


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, Lead] = {}

    async def add(self, lead: Lead) -> None:
        self.rows[lead.id] = lead

    async def get(self, lead_id: str) -> Lead | None:
        return self.rows.get(lead_id)

    async def list(self, status: str | None, limit: int) -> list[Lead]:
        rows = [r for r in self.rows.values() if status in (None, r.status)]
        return rows[:limit]

    async def save_status(self, lead: Lead, expected_status: str) -> bool:
        self.rows[lead.id] = lead
        return True


class RecordingNotifier:
    def __init__(self) -> None:
        self.seen: list[Lead] = []

    async def notify(self, lead: Lead) -> None:
        self.seen.append(lead)


def test_signature_matches_known_vector() -> None:
    body = b'{"a":1}'
    expected = hmac.new(b"s3cret", b"1700000000." + body, hashlib.sha256).hexdigest()
    assert sign("s3cret", "1700000000", body) == f"sha256={expected}"
    assert sign("s3cret", "1700000001", body) != f"sha256={expected}"


async def test_webhook_sends_signed_body_and_swallows_failure() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    lead = Lead.create(summary="x", profile={}, email="a@b.co")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await HmacWebhookNotifier("http://hook.test/x", "k", client=client).notify(lead)
    request = captured[0]
    timestamp = request.headers["X-REIC-Timestamp"]
    assert timestamp.isdigit()
    assert request.headers["X-REIC-Signature"] == sign("k", timestamp, request.content)
    assert json.loads(request.content)["id"] == lead.id

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as client:
        await HmacWebhookNotifier("http://hook.test/x", "k", client=client).notify(lead)


async def test_service_create_list_update() -> None:
    notifier = RecordingNotifier()
    service = HandoffService(MemoryStore(), notifier)
    created = await service.create_lead(LEAD)
    assert created["status"] == "new"
    assert len(notifier.seen) == 1
    assert [x["id"] for x in await service.list_leads("new", 10)] == [created["lead_id"]]
    assert await service.list_leads("closed", 10) == []
    updated = await service.update_status(created["lead_id"], "contacted")
    assert updated["status"] == "contacted"
    await service.update_status(created["lead_id"], "closed")
    with pytest.raises(InvalidStatusTransitionError):
        await service.update_status(created["lead_id"], "new")
    with pytest.raises(LeadNotFoundError):
        await service.update_status("nope", "closed")


async def test_validation() -> None:
    service = HandoffService(MemoryStore(), RecordingNotifier())
    no_contact = {k: v for k, v in LEAD.items() if k != "phone"}
    for bad in (
        no_contact,
        {**LEAD, "goal": "flip"},
        {**LEAD, "email": "nope"},
        {**LEAD, "unknown": 1},
        {"phone": "1"},
        {**LEAD, "profile": {"blob": "x" * 20_000}},
        {**LEAD, "unit_codes": ["U" * 65]},
        {**LEAD, "budget_egp": 10**20},
    ):
        with pytest.raises(LeadValidationError):
            await service.create_lead(bad)
    with pytest.raises(LeadValidationError):
        await service.list_leads("weird")


async def test_concurrent_status_change_is_rejected() -> None:
    class StaleStore(MemoryStore):
        async def save_status(self, lead: Lead, expected_status: str) -> bool:
            return False

    service = HandoffService(StaleStore(), RecordingNotifier())
    created = await service.create_lead(LEAD)
    with pytest.raises(InvalidStatusTransitionError):
        await service.update_status(created["lead_id"], "contacted")


def test_webhook_needs_secret() -> None:
    def notifier(secret: str | None) -> object:
        settings = Settings(
            webhook_url="http://hook.test/x",
            webhook_secret=SecretStr(secret) if secret else None,
        )
        return build_handoff_service(None, settings)._notifier  # type: ignore[arg-type]

    assert isinstance(notifier(None), NullNotifier)
    assert isinstance(notifier("k"), HmacWebhookNotifier)


def _client(key: str | None) -> Iterator[TestClient[Any]]:
    settings = Settings(broker_api_key=SecretStr(key) if key else None)
    service = HandoffService(MemoryStore(), RecordingNotifier())
    with TestClient(app=Litestar([build_handoff_router(service, settings)])) as c:
        yield c


@pytest.fixture
def keyed() -> Iterator[TestClient[Any]]:
    yield from _client("k-123")


@pytest.fixture
def unkeyed() -> Iterator[TestClient[Any]]:
    yield from _client(None)


def test_public_post_and_validation(keyed: TestClient[Any]) -> None:
    r = keyed.post("/leads", json=LEAD)
    assert r.status_code == 201
    assert r.json()["status"] == "new"
    assert keyed.post("/leads", json={"summary": "no contact", "profile": {}}).status_code == 400


def test_guard(keyed: TestClient[Any], unkeyed: TestClient[Any]) -> None:
    assert keyed.get("/broker/leads").status_code == 401
    assert keyed.get("/broker/leads", headers={"X-API-Key": "wrong"}).status_code == 401
    assert unkeyed.get("/broker/leads", headers={"X-API-Key": "k-123"}).status_code == 503
    ok = keyed.get("/broker/leads", headers={"X-API-Key": "k-123"})
    assert ok.status_code == 200
    assert ok.json() == []


def test_broker_patch(keyed: TestClient[Any]) -> None:
    headers = {"X-API-Key": "k-123"}
    lead_id = keyed.post("/leads", json=LEAD).json()["lead_id"]
    r = keyed.patch(f"/broker/leads/{lead_id}", json={"status": "qualified"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "qualified"
    assert (
        keyed.patch(f"/broker/leads/{lead_id}", json={"status": "x"}, headers=headers).status_code
        == 400
    )
    assert (
        keyed.patch(f"/broker/leads/{lead_id}", json={"status": "new"}, headers=headers).status_code
        == 409
    )
    assert (
        keyed.patch("/broker/leads/zzz", json={"status": "closed"}, headers=headers).status_code
        == 404
    )
    assert keyed.patch(f"/broker/leads/{lead_id}", json={"status": "closed"}).status_code == 401
