"""Chat sessions: runs a turn through the agent engine and streams events to the client."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from reic.modules.companion.application.prompts import build_instruction
from reic.modules.companion.application.toolbox import SessionState, ToolBox
from reic.modules.companion.domain.errors import SessionNotFoundError
from reic.modules.companion.domain.events import ChatEvent
from reic.modules.companion.domain.grounding import ungrounded_numbers
from reic.modules.companion.domain.profile import BuyerProfile, Language
from reic.modules.companion.ports.backend import CompanionBackend, ReportRenderer
from reic.modules.companion.ports.engine import AgentEngine
from reic.modules.companion.ports.session_store import SessionStore

log = logging.getLogger(__name__)

MAX_SESSIONS = 2000
MAX_MESSAGE_CHARS = 2000
MAX_STORED_MESSAGES = 60
MAX_STORED_RESULTS = 40
RECAP_MESSAGES = 8
RECAP_CHARS = 400
# Below the host's request limit (300 s on Vercel), so a stuck model ends in a clean error.
TURN_TIMEOUT_S = 240.0

_GROUNDING_NOTE = {
    "en": "\n\n_Note: some figures above could not be traced to the calculators; "
    "rely on the cards and charts for exact numbers._",
    "ar": "\n\n_ملاحظة: بعض الأرقام أعلاه لم تأتِ مباشرة من الحاسبات؛ "
    "اعتمد على البطاقات والرسوم للأرقام الدقيقة._",
}
_FAILURE = {
    "en": "Sorry, I could not finish that. Please try again in a moment.",
    "ar": "عذرًا، لم أتمكن من إكمال ذلك. حاول مرة أخرى بعد قليل.",
}


class ChatService:
    def __init__(
        self,
        engine: AgentEngine,
        backend: CompanionBackend,
        reports: ReportRenderer | None = None,
        *,
        pdf_available: bool = False,
        store: SessionStore | None = None,
    ) -> None:
        self._engine = engine
        self._backend = backend
        self._reports = reports
        self._pdf_available = pdf_available
        self._store = store
        self._sessions: dict[str, SessionState] = {}

    def _remember(self, state: SessionState) -> None:
        if len(self._sessions) >= MAX_SESSIONS:
            self._sessions.pop(next(iter(self._sessions)))
        self._sessions[state.session_id] = state

    def create_session(self, language: Language = "en") -> str:
        session_id = uuid.uuid4().hex
        self._remember(SessionState(session_id, BuyerProfile(language=language)))
        return session_id

    async def open_session(self, language: Language = "en") -> str:
        """A new session, saved right away so any instance can serve its next request."""
        session_id = self.create_session(language)
        await self._save(self._sessions[session_id])
        return session_id

    def state(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None

    async def load(self, session_id: str) -> SessionState:
        """The session from memory, or restored from the store after a restart."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        data = await self._store.load(session_id) if self._store else None
        if data is None:
            raise SessionNotFoundError(session_id)
        state = SessionState(
            session_id,
            BuyerProfile.from_dict(data.get("profile") or {}),
            artifacts=data.get("artifacts") or {},
            lead_id=data.get("lead_id"),
            messages=data.get("messages") or [],
            results=data.get("results") or [],
        )
        state.recap = _recap(state.messages)
        self._remember(state)
        return state

    async def _save(self, state: SessionState) -> None:
        if self._store is None:
            return
        state.messages = state.messages[-MAX_STORED_MESSAGES:]
        state.results = state.results[-MAX_STORED_RESULTS:]
        try:
            await self._store.save(
                state.session_id,
                {
                    "language": state.profile.language,
                    "profile": state.profile.to_dict(),
                    "artifacts": state.artifacts,
                    "lead_id": state.lead_id,
                    "messages": state.messages,
                    "results": state.results,
                },
            )
        except Exception:  # the buyer already has the answer; keep serving from memory
            log.exception("saving chat session failed", extra={"session_id": state.session_id})

    async def delete_session(self, session_id: str) -> None:
        """Forget a conversation (the buyer's "new chat"). Leads already sent are kept."""
        self._sessions.pop(session_id, None)
        if self._store is not None:
            await self._store.delete(session_id)

    async def transcript(self, session_id: str) -> dict[str, Any]:
        state = await self.load(session_id)
        return {
            "session_id": session_id,
            "language": state.profile.language,
            "profile": state.profile.to_dict(),
            "messages": state.messages,
        }

    async def send(
        self, session_id: str, message: str, language: Language | None = None
    ) -> AsyncIterator[ChatEvent]:
        state = await self.load(session_id)
        if language and language != state.profile.language:
            state.profile = state.profile.merge(language=language)
        lang = state.profile.language
        message = message[:MAX_MESSAGE_CHARS]
        toolbox = ToolBox(state, self._backend, pdf_available=self._pdf_available)
        answer: list[str] = []
        shown: list[dict[str, Any]] = []
        try:
            async with asyncio.timeout(TURN_TIMEOUT_S):
                async for event in self._engine.run_turn(
                    session_id,
                    message,
                    build_instruction(state.profile, state.recap),
                    toolbox.tools(),
                ):
                    if event.kind == "delta":
                        answer.append(event.data["text"])
                    yield event
                    if event.kind == "tool" and event.data.get("status") == "finished":
                        while toolbox.pending:
                            kind, data = toolbox.pending.pop(0)
                            shown.append({"kind": kind, "data": data})
                            yield ChatEvent.artifact(kind, data)
        except Exception:
            log.exception("chat turn failed", extra={"session_id": session_id})
            yield ChatEvent("error", {"message": _FAILURE[lang]})
            return
        while toolbox.pending:
            kind, data = toolbox.pending.pop(0)
            shown.append({"kind": kind, "data": data})
            yield ChatEvent.artifact(kind, data)
        # Numbers the buyer gave and results from earlier turns are traced too.
        sources = [*state.results, *toolbox.results, {"message": message}]
        missing = ungrounded_numbers("".join(answer), sources)
        if missing:
            log.warning("ungrounded numbers in answer: %s", missing[:5])
            answer.append(_GROUNDING_NOTE[lang])
            yield ChatEvent.delta(_GROUNDING_NOTE[lang])
        state.results.extend(toolbox.results)
        state.messages.append({"role": "user", "text": message})
        state.messages.append({"role": "assistant", "text": "".join(answer), "artifacts": shown})
        await self._save(state)
        yield ChatEvent("done", {})

    def report_payload(self, session_id: str, language: str | None = None) -> dict[str, Any]:
        state = self.state(session_id)
        payload: dict[str, Any] = {
            "language": language or state.profile.language,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "profile": state.profile.to_dict(),
        }
        payload.update(state.artifacts)
        payload.pop("report", None)
        payload.pop("handoff", None)
        if "shortlist" in payload:  # the report takes the unit list itself
            payload["shortlist"] = payload["shortlist"].get("units", [])
        return payload

    def render_report(self, session_id: str, language: str, fmt: str) -> bytes | str | None:
        if self._reports is None:
            return None
        payload = self.report_payload(session_id, language)
        if fmt == "pdf":
            return self._reports.render_pdf(payload, language)
        return self._reports.render_html(payload, language)


def _recap(messages: list[dict[str, Any]]) -> str | None:
    lines = [
        f"{m['role']}: {str(m.get('text') or '')[:RECAP_CHARS]}"
        for m in messages[-RECAP_MESSAGES:]
        if m.get("text")
    ]
    return "\n".join(lines) or None
