"""The chat over PydanticAI: it converses and chooses when to call the base's tools, which the caller binds; where
anything goes is decided inside those tools, never here (rule 6). Its reply is the AI SDK's UI message stream."""

from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from contextlib import aclosing
from typing import Any, Literal, cast

from pydantic_ai import Agent, ToolReturn
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResult
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.ui import NativeEvent
from pydantic_ai.ui.vercel_ai import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DataChunk,
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    MessageMetadataChunk,
    StartChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)

from acervo.core.ids import uuid7
from acervo.model_clients.llm_writer import prompt

# An earlier message of the conversation: who said it, and what.
Turn = tuple[Literal["person", "acervo"], str]
Tool = Callable[..., Awaitable[Any]]
# One chunk of the AI SDK UI message stream, as its JSON (`[DONE]` for the last).
Chunk = str
# Gets the reply's text once the run ended well; gives the chunks that go before `finish`.
Finish = Callable[[str], Awaitable[Sequence[Chunk]]]

# The AI SDK major the web app uses (`ai` 6): the wire of its UI message stream.
SDK_VERSION: Literal[6] = 6


class _Encoded(BaseChunk):
    """A chunk the caller encoded already, passed through the event stream as is."""

    type: Literal["encoded"] = "encoded"
    wire: str

    def encode(self, sdk_version: int) -> str:
        return self.wire


def with_data(value: Any, *chunks: Chunk) -> ToolReturn:
    """A tool's result for the model, with `data-*` chunks for the UI that the model never sees."""
    return ToolReturn(return_value=value, metadata=[DataChunk.model_validate_json(chunk) for chunk in chunks])


def start_chunk(message_id: str) -> Chunk:
    return StartChunk(message_id=message_id).encode(SDK_VERSION)


def text_chunks(text: str) -> list[Chunk]:
    """A text part, whole."""
    id = str(uuid7())
    chunks: list[BaseChunk] = [TextStartChunk(id=id), TextDeltaChunk(id=id, delta=text), TextEndChunk(id=id)]
    return [chunk.encode(SDK_VERSION) for chunk in chunks]


def metadata_chunk(metadata: dict[str, Any]) -> Chunk:
    return MessageMetadataChunk(message_metadata=metadata).encode(SDK_VERSION)


def end_chunks(error: str | None = None) -> list[Chunk]:
    """The end of a reply: its error first when it failed."""
    chunks: list[BaseChunk] = [ErrorChunk(error_text=error)] if error is not None else []
    chunks += [FinishChunk(finish_reason="error" if error is not None else "stop"), DoneChunk()]
    return [chunk.encode(SDK_VERSION) for chunk in chunks]


class ChatAgent:
    def __init__(self, model: Model | str) -> None:
        # A model string is resolved at the first call, so building the agent needs no provider key.
        self._agent: Agent[None, str] = Agent(
            model, output_type=str, instructions=prompt("chat"), defer_model_check=True
        )

    async def stream(
        self, message: str, history: Sequence[Turn], tools: Sequence[Tool], *, message_id: str, finish: Finish
    ) -> AsyncIterator[Chunk]:
        """The reply to `message` as UI message stream chunks, from `start` to `[DONE]`. `finish` gets all the text
        the model wrote in the run, also before and between tool calls, so what streamed is what is kept. A run that
        fails raises what failed it, after the chunks that close what was open; the caller ends the stream."""
        failure: list[Exception] = []

        async def events() -> AsyncIterator[NativeEvent]:
            try:
                async with self._agent.run_stream_events(
                    message,
                    message_history=_history(history),
                    # One at a time: the tools share the caller's database session.
                    toolsets=[FunctionToolset(list(tools), sequential=True)],
                ) as run:
                    async for event in run:
                        yield event
            except Exception as exc:
                failure.append(exc)
                raise

        async def complete(result: AgentRunResult[str]) -> AsyncIterator[BaseChunk]:
            try:
                chunks = await finish(_text(result.new_messages()) or result.output)
            except Exception as exc:
                failure.append(exc)
                raise
            for chunk in chunks:
                yield _Encoded(wire=chunk)

        encoder = VercelAIEventStream(sdk_version=SDK_VERSION, server_message_id=message_id)
        stream = cast(AsyncGenerator[BaseChunk], encoder.transform_stream(events(), on_complete=complete))
        async with aclosing(stream) as chunks:
            async for chunk in chunks:
                if isinstance(chunk, ErrorChunk):
                    raise failure[0] if failure else RuntimeError(chunk.error_text)
                yield chunk.encode(SDK_VERSION)


def _history(turns: Sequence[Turn]) -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content=text)])
        if role == "person"
        else ModelResponse(parts=[TextPart(text)])
        for role, text in turns
    ]


def _text(messages: Sequence[ModelMessage]) -> str:
    """Every text the model wrote in the run, a paragraph per part."""
    parts = [
        part.content
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, TextPart) and part.content
    ]
    return "\n\n".join(parts).strip()
