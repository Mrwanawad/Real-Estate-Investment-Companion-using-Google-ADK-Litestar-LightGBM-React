"""Events streamed to the chat client (one SSE event each)."""

from dataclasses import dataclass, field
from typing import Any, Literal

EventKind = Literal["tool", "delta", "artifact", "done", "error"]


@dataclass(frozen=True, slots=True)
class ChatEvent:
    kind: EventKind
    data: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def delta(text: str) -> "ChatEvent":
        return ChatEvent("delta", {"text": text})

    @staticmethod
    def tool(name: str, status: str) -> "ChatEvent":
        return ChatEvent("tool", {"name": name, "status": status})

    @staticmethod
    def artifact(kind: str, data: dict[str, Any]) -> "ChatEvent":
        return ChatEvent("artifact", {"kind": kind, "data": data})
