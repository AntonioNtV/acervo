import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator, Sequence
from typing import Any

from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from acervo.core.settings import RetrievalLimits
from acervo.model_clients.chat_agent import ChatAgent, Chunk, Tool


async def _finish(text: str) -> list[Chunk]:
    return []


async def _reply(model: FunctionModel, reads: Sequence[Tool], writes: Sequence[Tool]) -> list[Chunk]:
    stream = ChatAgent(model).stream("oi", [], reads, writes, limits=RetrievalLimits(), message_id="m", finish=_finish)
    return [chunk async for chunk in stream]


async def test_reads_called_in_one_step_run_at_once_and_writes_one_at_a_time() -> None:
    running: defaultdict[str, int] = defaultdict(int)
    most: defaultdict[str, int] = defaultdict(int)

    async def runs(name: str) -> None:
        running[name] += 1
        most[name] = max(most[name], running[name])
        await asyncio.sleep(0.05)
        running[name] -= 1

    async def abrir(ref: str) -> str:
        await runs("abrir")
        return ref

    async def move(node_id: str) -> str:
        await runs("move")
        return node_id

    turns: list[Any] = [
        [("abrir", {"ref": "a"}), ("abrir", {"ref": "b"})],
        [("move", {"node_id": "a"}), ("move", {"node_id": "b"})],
        "Pronto.",
    ]

    async def script(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        turn = turns.pop(0)
        if isinstance(turn, str):
            yield turn
            return
        yield {index: DeltaToolCall(name, json.dumps(args)) for index, (name, args) in enumerate(turn)}

    await _reply(FunctionModel(stream_function=script), [abrir], [move])

    assert dict(most) == {"abrir": 2, "move": 1}


async def test_after_the_tool_steps_the_model_is_offered_no_tools() -> None:
    offered: list[list[str]] = []

    async def abrir(ref: str) -> str:
        return ref

    async def always_calls(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        offered.append([tool.name for tool in info.function_tools])
        if info.function_tools:
            yield {0: DeltaToolCall("abrir", json.dumps({"ref": "a"}))}
        else:
            yield "Pronto."

    await _reply(FunctionModel(stream_function=always_calls), [abrir], [])

    limits = RetrievalLimits()
    assert len(offered) == limits.llm_steps
    assert offered == [["abrir"]] * limits.llm_tool_steps + [[]]
