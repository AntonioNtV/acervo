import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings, Thresholds
from acervo.domain.decisions import Answers, Choice, Question
from acervo.model_clients.fakes import FakeDecider, FakeProbs, FakeWriter
from acervo.services.storage import Storage

RUNNER = Path(__file__).resolve().parents[2] / "evals" / "ai1" / "run.py"
GUARDAR = [0.05, 0.9, 0.03, 0.02]


def _runner() -> ModuleType:
    """evals/ is not a package: the runner is loaded from its file, as `make eval-ai1` runs it."""
    spec = importlib.util.spec_from_file_location("ai1_run", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ai1 = _runner()


@dataclass
class FirstOption(FakeDecider):
    """Answers what `fixed` lacks: a Choice with its first option, a Noul with "no". The descents of a fact and of a
    PDF share an id with different options, so the defaults are made for each call."""

    fixed: dict[str, FakeProbs] = field(default_factory=dict)

    async def ask(self, state: str, questions: Sequence[Question]) -> Answers:
        self.table = {
            question.id: [1.0] + [0.0] * (len(question.options) - 1) if isinstance(question, Choice) else 0.1
            for question in questions
        } | self.fixed
        return await super().ask(state, questions)


def test_the_cases_load_and_match_the_seed() -> None:
    base, cases = ai1.load()

    assert ai1.check(base, cases) == []
    assert len(cases) == 20
    expected = {part.outcome for case in cases for part in case.expect}
    assert expected == set(get_args(ai1.Outcome))
    assert any(len(case.expect) > 1 and not case.files for case in cases), "a split case"


async def test_the_runner_runs_every_case_end_to_end_with_the_fakes(
    session_factory: async_sessionmaker[AsyncSession], storage: Settings, fake_writer: FakeWriter
) -> None:
    base, cases = ai1.load()
    decider = FirstOption(fixed={"intent": GUARDAR, "two_subjects": 0.1})

    results = await ai1.run(session_factory, Storage(storage), decider, fake_writer, Thresholds(), base, cases)

    assert [result.case.id for result in results] == [case.id for case in cases]
    assert {result.status for result in results} == {"done"}
    assert all(result.decisions and result.seen for result in results)
    printed = ai1.report(results, "fake")
    assert all(case.id in printed for case in cases)
    assert "right place, first path:" in printed
