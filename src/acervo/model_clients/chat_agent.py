"""The chat over PydanticAI: it converses and chooses when to call the base's tools, which the caller binds; where
anything goes is decided inside those tools, never here (rule 6)."""

from collections.abc import AsyncIterable, Awaitable, Callable, Sequence
from typing import Any, Literal

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.toolsets import FunctionToolset

from acervo.model_clients.llm_writer import prompt

# An earlier message of the conversation: who said it, and what.
Turn = tuple[Literal["person", "acervo"], str]
Tool = Callable[..., Awaitable[Any]]
OnText = Callable[[str], Awaitable[None]]


class ChatAgent:
    def __init__(self, model: Model | str) -> None:
        # A model string is resolved at the first call, so building the agent needs no provider key.
        self._agent: Agent[None, str] = Agent(
            model, output_type=str, instructions=prompt("chat"), defer_model_check=True
        )

    async def reply(self, message: str, history: Sequence[Turn], tools: Sequence[Tool], on_text: OnText) -> str:
        """The reply to `message`, its text handed to `on_text` as it is written. It is all the text the model wrote
        in the run, also before and between tool calls, so what streamed is what is kept."""
        written: list[str] = []

        async def stream(_: RunContext[None], events: AsyncIterable[AgentStreamEvent]) -> None:
            new_part = False
            async for event in events:
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    new_part, text = True, event.part.content
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    text = event.delta.content_delta
                else:
                    continue
                if not text:
                    continue
                if new_part and written:
                    text = f"\n\n{text}"
                new_part = False
                written.append(text)
                await on_text(text)

        result = await self._agent.run(
            message,
            message_history=_history(history),
            # One at a time: the tools share the caller's database session.
            toolsets=[FunctionToolset(list(tools), sequential=True)],
            event_stream_handler=stream,
        )
        return "".join(written).strip() or result.output


def _history(turns: Sequence[Turn]) -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content=text)])
        if role == "person"
        else ModelResponse(parts=[TextPart(text)])
        for role, text in turns
    ]
