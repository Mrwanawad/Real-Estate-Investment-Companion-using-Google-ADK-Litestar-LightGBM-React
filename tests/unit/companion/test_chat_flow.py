from typing import Any

import pytest

from reic.modules.companion.adapters.outbound.adk_engine import AdkEngine
from reic.modules.companion.adapters.outbound.llm import FakeLlm, parse_buyer_message
from reic.modules.companion.application.chat import ChatService
from reic.modules.companion.domain.events import ChatEvent

UNIT = {
    "code": "NC-001",
    "price_egp": 4_800_000,
    "area_id": "NC",
    "delivery_year": 2027,
    "plans": [],
}


class StubBackend:
    def __init__(self) -> None:
        self.leads: list[dict[str, Any]] = []

    async def shortlist(self, criteria: dict[str, Any], goal: str, limit: int) -> dict[str, Any]:
        assert criteria["budget_max_egp"] == 5_000_000
        assert goal == "rent"
        return {
            "units": [
                {
                    "code": "NC-001",
                    "project_name": "Palm Yard",
                    "area_name": "New Cairo",
                    "type": "apartment",
                    "bedrooms": 3,
                    "bua_m2": 150,
                    "price_egp": 4_800_000,
                    "delivery_year": 2027,
                    "developer_tier": "A",
                    "score": 0.81,
                    "reasons": ["fits the budget"],
                }
            ]
        }

    async def unit(self, code: str) -> dict[str, Any] | None:
        return UNIT if code == "NC-001" else None

    async def compare_financing(self, unit: dict[str, Any]) -> dict[str, Any]:
        return {"unit_code": unit["code"], "cheapest_label": "Cash", "options": []}

    async def project_returns(
        self, unit: dict[str, Any], horizon_years: int, goal: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        projection = {
            "unit_code": unit["code"],
            "horizon_years": horizon_years,
            "value": {"p10": 5_000_000.0, "p50": 7_000_000.0, "p90": 9_500_000.0},
            "rent": {"monthly_p50": 21000, "gross_yield": 0.0525},
            "irr": {"p10": 0.02, "p50": 0.12, "p90": 0.2},
            "prob_loss": 0.08,
            "break_even_year": 3,
        }
        risks = {"items": [{"kind": "delivery", "level": "low", "explanation_en": "ok"}]}
        return projection, risks

    async def search_knowledge(self, query: str, language: str) -> dict[str, Any]:
        return {
            "items": [
                {
                    "doc_id": "cancel-en",
                    "title": "Cancellation policy",
                    "snippet": "Refund within 14 days.",
                    "text": "Refund within 14 days.",
                }
            ]
        }

    async def create_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        self.leads.append(lead)
        return {"lead_id": "lead-1", "status": "new"}


@pytest.fixture
def chat() -> tuple[ChatService, StubBackend]:
    backend = StubBackend()
    return ChatService(AdkEngine(FakeLlm(), stream=False), backend), backend


async def _collect(chat: ChatService, sid: str, message: str) -> list[ChatEvent]:
    return [event async for event in chat.send(sid, message)]


def test_parse_buyer_message() -> None:
    facts = parse_buyer_message("I have 5M EGP, want to rent it out in New Cairo for 5 years")
    assert facts == {
        "goal": "rent",
        "areas": ["New Cairo"],
        "horizon_years": 5,
        "budget_egp": 5_000_000,
    }
    assert parse_buyer_message("call me on 01012345678")["phone"] == "01012345678"
    arabic = parse_buyer_message("معايا 5 مليون جنيه وعايز أأجّر في القاهرة الجديدة، لمدة 5 سنين")
    assert arabic["goal"] == "rent" and arabic["budget_egp"] == 5_000_000


async def test_full_turn_streams_tools_artifacts_and_grounded_text(chat) -> None:
    service, _ = chat
    sid = service.create_session("en")
    events = await _collect(
        service, sid, "I have 5M EGP, want to rent it out in New Cairo for 5 years"
    )
    kinds = [e.kind for e in events]
    assert kinds[-1] == "done"
    started = [e.data["name"] for e in events if e.kind == "tool" and e.data["status"] == "started"]
    assert started == ["update_profile", "search_units", "compare_financing", "project_returns"]
    artifacts = [e.data["kind"] for e in events if e.kind == "artifact"]
    assert artifacts == ["shortlist", "financing", "projection", "risks"]
    text = "".join(e.data["text"] for e in events if e.kind == "delta")
    assert "NC-001" in text and "7,000,000" in text
    assert "could not be traced" not in text  # every number came from a tool
    assert service.state(sid).profile.budget_egp == 5_000_000


async def test_clarifies_when_goal_and_budget_missing(chat) -> None:
    service, _ = chat
    sid = service.create_session("en")
    events = await _collect(service, sid, "hello, I want to buy an apartment")
    text = "".join(e.data["text"] for e in events if e.kind == "delta")
    assert "goal" in text and "budget" in text
    assert not [e for e in events if e.kind == "artifact"]


async def test_knowledge_question_cites_sources(chat) -> None:
    service, _ = chat
    sid = service.create_session("en")
    events = await _collect(service, sid, "What is the cancellation refund policy?")
    citations = [e.data for e in events if e.kind == "artifact" and e.data["kind"] == "citations"]
    assert citations[0]["data"]["items"][0]["doc_id"] == "cancel-en"


async def test_handoff_needs_contact_then_creates_one_lead(chat) -> None:
    service, backend = chat
    sid = service.create_session("en")
    first = await _collect(service, sid, "I want to talk to a broker")
    assert "phone" in "".join(e.data["text"] for e in first if e.kind == "delta")
    assert backend.leads == []
    second = await _collect(service, sid, "Sure, contact me on 01012345678")
    handoff = [e for e in second if e.kind == "artifact" and e.data["kind"] == "handoff"]
    assert handoff and backend.leads[0]["phone"] == "01012345678"


async def test_report_payload_collects_artifacts(chat) -> None:
    service, _ = chat
    sid = service.create_session("en")
    await _collect(service, sid, "I have 5M EGP, want to rent it out in New Cairo for 5 years")
    events = await _collect(service, sid, "Please build the report")
    report = [e.data["data"] for e in events if e.kind == "artifact" and e.data["kind"] == "report"]
    assert report[0]["url_html"].startswith(f"/reports/{sid}")
    payload = service.report_payload(sid)
    assert {"profile", "shortlist", "financing", "projection", "risks"} <= payload.keys()
    assert isinstance(payload["shortlist"], list)


async def test_backend_failure_is_reported_not_fatal() -> None:
    class Broken(StubBackend):
        async def compare_financing(self, unit: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("db down")

    service = ChatService(AdkEngine(FakeLlm(), stream=False), Broken())
    sid = service.create_session("en")
    events = await _collect(
        service, sid, "I have 5M EGP, want to rent it out in New Cairo for 5 years"
    )
    assert events[-1].kind == "done"
    assert not [e for e in events if e.kind == "error"]


class StreamingFakeLlm(FakeLlm):
    """Like Gemini in SSE mode: each response arrives as a partial chunk, then the aggregate."""

    async def generate_content_async(self, llm_request, stream=False):  # type: ignore[no-untyped-def]
        response = self._next(llm_request)
        if stream:
            yield response.model_copy(update={"partial": True})
        yield response


async def test_streamed_tool_calls_are_reported_once() -> None:
    service = ChatService(AdkEngine(StreamingFakeLlm(), stream=True), StubBackend())
    sid = service.create_session("en")
    events = await _collect(
        service, sid, "I have 5M EGP, want to rent it out in New Cairo for 5 years"
    )
    started = [e.data["name"] for e in events if e.kind == "tool" and e.data["status"] == "started"]
    assert started == ["update_profile", "search_units", "compare_financing", "project_returns"]
    assert events[-1].kind == "done"


class MemoryStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def load(self, session_id: str) -> dict[str, Any] | None:
        return self.docs.get(session_id)

    async def save(self, session_id: str, data: dict[str, Any]) -> None:
        self.docs[session_id] = data


async def test_session_survives_a_restart_with_transcript_and_recap() -> None:
    store = MemoryStore()
    first = ChatService(AdkEngine(FakeLlm(), stream=False), StubBackend(), store=store)
    sid = first.create_session("en")
    await _collect(first, sid, "I have 5M EGP, want to rent it out in New Cairo for 5 years")
    assert sid in store.docs

    restarted = ChatService(AdkEngine(FakeLlm(), stream=False), StubBackend(), store=store)
    transcript = await restarted.transcript(sid)
    assert [m["role"] for m in transcript["messages"]] == ["user", "assistant"]
    kinds = [a["kind"] for a in transcript["messages"][1]["artifacts"]]
    assert kinds == ["shortlist", "financing", "projection", "risks"]
    state = await restarted.load(sid)
    assert state.profile.budget_egp == 5_000_000 and state.recap
    payload = restarted.report_payload(sid)
    assert {"shortlist", "projection"} <= payload.keys()


async def test_unknown_session_is_not_found() -> None:
    from reic.modules.companion.domain.errors import SessionNotFoundError

    service = ChatService(AdkEngine(FakeLlm(), stream=False), StubBackend(), store=MemoryStore())
    with pytest.raises(SessionNotFoundError):
        await service.load("missing")


async def test_lead_needs_consent() -> None:
    from reic.modules.companion.application.toolbox import SessionState, ToolBox
    from reic.modules.companion.domain.profile import BuyerProfile

    backend = StubBackend()
    state = SessionState("s1", BuyerProfile(phone="01012345678"))
    box = ToolBox(state, backend)
    refused = await box.create_lead("wants a call", buyer_consented=False)
    assert "error" in refused and backend.leads == []
    created = await box.create_lead("wants a call", buyer_consented=True)
    assert created["lead_id"] == "lead-1"
    assert backend.leads[0]["profile"]["consent_at"]


async def test_numbers_from_the_buyer_and_earlier_turns_count_as_grounded() -> None:
    from reic.modules.companion.domain.grounding import ungrounded_numbers

    assert ungrounded_numbers("Your 5M budget", [{"message": "I have 5,000,000 EGP"}]) == []


async def test_opened_session_is_saved_before_the_first_message() -> None:
    store = MemoryStore()
    service = ChatService(AdkEngine(FakeLlm(), stream=False), StubBackend(), store=store)
    sid = await service.open_session("ar")
    other = ChatService(AdkEngine(FakeLlm(), stream=False), StubBackend(), store=store)
    assert (await other.load(sid)).profile.language == "ar"


async def test_stuck_model_ends_the_turn_with_an_error(monkeypatch) -> None:
    import asyncio

    from reic.modules.companion.application import chat as chat_module

    class StuckEngine:
        async def run_turn(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            await asyncio.sleep(10)
            yield ChatEvent.delta("never")

    monkeypatch.setattr(chat_module, "TURN_TIMEOUT_S", 0.05)
    service = ChatService(StuckEngine(), StubBackend())  # type: ignore[arg-type]
    sid = service.create_session("en")
    events = await _collect(service, sid, "hello")
    assert [e.kind for e in events] == ["error"]
