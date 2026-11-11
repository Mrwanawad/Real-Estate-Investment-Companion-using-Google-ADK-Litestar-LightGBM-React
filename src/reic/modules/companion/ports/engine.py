from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, Protocol

from reic.modules.companion.domain.events import ChatEvent

ToolFunction = Callable[..., Awaitable[dict[str, Any]]]


class AgentEngine(Protocol):
    """Runs one user turn of the tool-using model and streams tool and text events.

    `tools` maps tool name to an async function; its signature and docstring describe the
    tool to the model. Only `tool` and `delta` events come out of the engine.
    """

    def run_turn(
        self,
        session_id: str,
        message: str,
        instruction: str,
        tools: Mapping[str, ToolFunction],
    ) -> AsyncIterator[ChatEvent]: ...
