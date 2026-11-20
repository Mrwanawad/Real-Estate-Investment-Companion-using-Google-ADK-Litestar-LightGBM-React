from typing import Any, Protocol


class SessionStore(Protocol):
    """Durable chat sessions, so a conversation survives restarts and machine stops.

    The stored dict holds language, profile, artifacts, lead_id, messages and results.
    """

    async def load(self, session_id: str) -> dict[str, Any] | None: ...

    async def save(self, session_id: str, data: dict[str, Any]) -> None: ...

    async def delete(self, session_id: str) -> None: ...
