"""Chat sessions: runs a turn through the agent engine and streams events to the client."""

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

log = logging.getLogger(__name__)

MAX_SESSIONS = 2000
MAX_MESSAGE_CHARS = 2000

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
    ) -> None:
        self._engine = engine
        self._backend = backend
        self._reports = reports
        self._pdf_available = pdf_available
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, language: Language = "en") -> str:
        if len(self._sessions) >= MAX_SESSIONS:
            self._sessions.pop(next(iter(self._sessions)))
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = SessionState(session_id, BuyerProfile(language=language))
        return session_id

    def state(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None

    async def send(
        self, session_id: str, message: str, language: Language | None = None
    ) -> AsyncIterator[ChatEvent]:
        state = self.state(session_id)
        if language and language != state.profile.language:
            state.profile = state.profile.merge(language=language)
        lang = state.profile.language
        toolbox = ToolBox(state, self._backend, pdf_available=self._pdf_available)
        answer: list[str] = []
        try:
            async for event in self._engine.run_turn(
                session_id,
                message[:MAX_MESSAGE_CHARS],
                build_instruction(state.profile),
                toolbox.tools(),
            ):
                if event.kind == "delta":
                    answer.append(event.data["text"])
                yield event
                if event.kind == "tool" and event.data.get("status") == "finished":
                    while toolbox.pending:
                        kind, data = toolbox.pending.pop(0)
                        yield ChatEvent.artifact(kind, data)
        except Exception:
            log.exception("chat turn failed", extra={"session_id": session_id})
            yield ChatEvent("error", {"message": _FAILURE[lang]})
            return
        while toolbox.pending:
            kind, data = toolbox.pending.pop(0)
            yield ChatEvent.artifact(kind, data)
        missing = ungrounded_numbers("".join(answer), toolbox.results)
        if missing:
            log.warning("ungrounded numbers in answer: %s", missing[:5])
            yield ChatEvent.delta(_GROUNDING_NOTE[lang])
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
