import json
from collections.abc import AsyncIterator
from typing import Literal

from litestar import Controller, Response, get, post
from litestar.exceptions import NotFoundException, ValidationException
from litestar.response import ServerSentEvent
from litestar.response.sse import ServerSentEventMessage
from pydantic import BaseModel, Field

from reic.modules.companion.application.chat import ChatService
from reic.modules.companion.domain.errors import SessionNotFoundError
from reic.modules.companion.domain.events import ChatEvent


class NewSession(BaseModel):
    language: Literal["en", "ar"] = "en"


class NewMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: Literal["en", "ar"] | None = None


def _sse(events: AsyncIterator[ChatEvent]) -> AsyncIterator[ServerSentEventMessage]:
    async def stream() -> AsyncIterator[ServerSentEventMessage]:
        async for event in events:
            yield ServerSentEventMessage(
                data=json.dumps(event.data, ensure_ascii=False, default=str),
                event=event.kind,
                sep="\n",
            )

    return stream()


class ChatController(Controller):
    path = "/chat/sessions"

    @post("/", status_code=201, sync_to_thread=False)
    def create(self, data: NewSession, chat: ChatService) -> dict[str, str]:
        return {"session_id": chat.create_session(data.language)}

    @post("/{session_id:str}/messages")
    async def message(
        self, session_id: str, data: NewMessage, chat: ChatService
    ) -> ServerSentEvent:
        try:
            chat.state(session_id)
        except SessionNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        stream = chat.send(session_id, data.message.strip(), data.language)
        return ServerSentEvent(_sse(stream), headers={"Cache-Control": "no-cache"})

    @get("/{session_id:str}/profile", sync_to_thread=False)
    def profile(self, session_id: str, chat: ChatService) -> dict[str, object]:
        try:
            return chat.state(session_id).profile.to_dict()
        except SessionNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc


class ReportController(Controller):
    path = "/reports"

    @get("/{session_id:str}", sync_to_thread=True)
    def report(
        self,
        session_id: str,
        chat: ChatService,
        lang: Literal["en", "ar"] = "en",
        format: Literal["html", "pdf"] = "html",  # noqa: A002 - public query name
    ) -> Response[bytes | str]:
        try:
            body = chat.render_report(session_id, lang, format)
        except SessionNotFoundError as exc:
            raise NotFoundException(str(exc)) from exc
        if body is None:
            raise ValidationException(f"{format} report is not available on this server")
        if format == "pdf":
            return Response(
                body,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="report-{lang}.pdf"'},
            )
        return Response(body, media_type="text/html; charset=utf-8")
