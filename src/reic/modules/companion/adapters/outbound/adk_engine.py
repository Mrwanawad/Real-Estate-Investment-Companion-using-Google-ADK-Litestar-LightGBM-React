"""AgentEngine on Google ADK: one LlmAgent per turn (fresh instruction), shared sessions."""

from collections.abc import AsyncIterator, Mapping

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from reic.modules.companion.domain.events import ChatEvent
from reic.modules.companion.ports.engine import ToolFunction

APP_NAME = "reic-companion"
USER_ID = "buyer"
MAX_LLM_CALLS = 12


class AdkEngine:
    def __init__(self, llm: BaseLlm, *, stream: bool = True) -> None:
        self._llm = llm
        self._stream = stream
        self._sessions = InMemorySessionService()

    def run_turn(
        self,
        session_id: str,
        message: str,
        instruction: str,
        tools: Mapping[str, ToolFunction],
    ) -> AsyncIterator[ChatEvent]:
        return self._run(session_id, message, instruction, tools)

    async def _run(
        self,
        session_id: str,
        message: str,
        instruction: str,
        tools: Mapping[str, ToolFunction],
    ) -> AsyncIterator[ChatEvent]:
        agent = LlmAgent(
            name="companion",
            model=self._llm,
            # A callable instruction skips ADK's {state} templating; the profile has braces.
            instruction=lambda _ctx: instruction,
            tools=[FunctionTool(fn) for fn in tools.values()],
        )
        runner = Runner(
            app_name=APP_NAME,
            agent=agent,
            session_service=self._sessions,
            auto_create_session=True,
        )
        config = RunConfig(
            streaming_mode=StreamingMode.SSE if self._stream else StreamingMode.NONE,
            max_llm_calls=MAX_LLM_CALLS,
        )
        streamed = False  # partial text already sent for the current model turn
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            run_config=config,
        ):
            # SSE mode repeats each call in the final aggregate; ADK runs the tool from that one.
            for call in [] if event.partial else event.get_function_calls():
                yield ChatEvent.tool(call.name or "", "started")
            for response in event.get_function_responses():
                yield ChatEvent.tool(response.name or "", "finished")
            if event.get_function_calls() or event.get_function_responses():
                streamed = False
                continue
            if not event.content or not event.content.parts:
                continue
            text = "".join(p.text or "" for p in event.content.parts if p.text and not p.thought)
            if not text:
                continue
            if event.partial:
                streamed = True
                yield ChatEvent.delta(text)
            elif not streamed:
                yield ChatEvent.delta(text)
            else:
                streamed = False  # the final aggregate of what was already streamed
