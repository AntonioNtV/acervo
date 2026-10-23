import importlib.util
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType

from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings, Thresholds
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.services.storage import Storage

RUNNER = Path(__file__).resolve().parents[2] / "evals" / "retrieval" / "run.py"


def _runner() -> ModuleType:
    """evals/ is not a package: the runner is loaded from its file, as `make eval-retrieval` runs it."""
    spec = importlib.util.spec_from_file_location("retrieval_run", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


retrieval = _runner()


async def _looks_then_answers(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
    """The chat's model, faked: it lists the root, then says it found nothing."""
    last = messages[-1]
    if isinstance(last, ModelRequest) and any(isinstance(part, ToolReturnPart) for part in last.parts):
        yield "Não está na base."
        return
    yield {0: DeltaToolCall("list_folder", "{}")}


def test_the_cases_load_and_match_the_seed() -> None:
    base, cases = retrieval.load()

    assert retrieval.check(base, cases) == []
    assert len(cases) >= 40
    assert sum(case.expect == "not_found" for case in cases) == 5
    assert any(case.after for case in cases)


async def test_the_runner_runs_every_case_end_to_end_with_the_fakes(
    session_factory: async_sessionmaker[AsyncSession], storage: Settings, fake_writer: FakeWriter
) -> None:
    base, cases = retrieval.load()
    chat = ChatAgent(FunctionModel(stream_function=_looks_then_answers))

    results = await retrieval.run(
        session_factory, Storage(storage), FakeDecider(), fake_writer, Thresholds(), chat, base, cases
    )

    assert [result.case.id for result in results] == [case.id for case in cases]
    assert {result.status for result in results} == {"done"}
    assert all(result.first_text is not None and result.total >= result.first_text for result in results)
    assert [result.hit for result in results] == [case.expect == "not_found" for case in cases]
    printed = retrieval.report(results, "fake", "function")
    assert all(case.id in printed for case in cases)
    assert "coverage 0/38 · abstention 5/5" in printed
