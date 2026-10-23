import importlib.util
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.ids import uuid7
from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.domain.decisions import Choice, Question
from acervo.domain.index import DocIndex
from acervo.model_clients.fakes import FakeDecider, FakeProbs
from acervo.pipeline.index.markdown import index_markdown
from acervo.pipeline.index.pdf import index_pdf
from acervo.repositories.uow import UnitOfWork
from acervo.services.search_service import Searched, SearchService

MakeTree = Callable[..., Awaitable[Any]]
PDF = "Bradesco/Auto/Tabela auto 2026.pdf"
TREE = {
    "Bradesco": {"Auto": ["Tabela auto 2026.pdf", "Regras.md"]},
    "Tabela antiga.pdf": None,
    "Contrato novo.pdf": None,
}
QUERY = "O que diz a página 137 da Tabela auto 2026?"
# The branches Jev prefers, by an option's title; the passage that answers.
WANTED = {"Atalho", "Bradesco", "Auto", "Tabela auto 2026.pdf", "Capítulo 7", "Seção 136"}
ANSWER = "Página 137."
LIMITS = RetrievalLimits()


def _make() -> ModuleType:
    """The fixtures folder is not a package: the builder is loaded from its file."""
    path = Path(__file__).resolve().parents[1] / "fixtures" / "pdfs" / "make.py"
    spec = importlib.util.spec_from_file_location("make_pdfs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pdf_index(tmp_path_factory: pytest.TempPathFactory) -> DocIndex:
    return index_pdf(_make().with_bookmarks(tmp_path_factory.mktemp("pdfs") / "tabela.pdf", pages=140), LIMITS)


def jev(state: str, question: Question) -> FakeProbs:
    if isinstance(question, Choice):
        raw = [1.0 if option.split("\n")[0] in WANTED else 0.01 for option in question.options[:-1]] + [0.0]
        return [weight / sum(raw) for weight in raw]
    return 3.0 if ANSWER in question.question else 0.0


@dataclass
class Env:
    uow: UnitOfWork
    tree: Any
    decider: FakeDecider
    service: SearchService

    async def search(self, run_id: UUID | None = None) -> Searched:
        return await self.service.search(self.tree.kb.id, QUERY, run_id=run_id or uuid7())

    def options(self) -> list[str]:
        return [
            option
            for _, questions in self.decider.calls
            for question in questions
            if isinstance(question, Choice)
            for option in question.options
        ]


@pytest.fixture
async def env(
    uow: UnitOfWork, session: AsyncSession, make_tree: MakeTree, fake_decider: FakeDecider, pdf_index: DocIndex
) -> AsyncIterator[Env]:
    tree = await make_tree(TREE)
    trashed = tree["Tabela antiga.pdf"]
    trashed.deleted_at, trashed.trashed_with = datetime.now(UTC), trashed.id
    await session.flush()
    fake_decider.answer = jev
    async with uow:
        indexes = {
            PDF: pdf_index,
            "Tabela antiga.pdf": pdf_index,
            "Bradesco/Auto/Regras.md": index_markdown("# Regras\n\n## Vistoria\nEm dois dias.\n", LIMITS),
        }
        for path, index in indexes.items():
            await uow.indexes.start(tree[path].id, "v1")
            await uow.indexes.finish(tree[path].id, "v1", index)
        await uow.commit()
        yield Env(uow, tree, fake_decider, SearchService(uow, fake_decider, LIMITS, Thresholds()))


async def test_a_question_answered_on_page_137_cites_that_page_with_a_highlight(env: Env) -> None:
    result = await env.search()

    found = next(evidence for evidence in result.evidence if ANSWER in evidence.text)
    assert found.node_id == env.tree[PDF].id
    assert found.path == ["Bradesco", "Auto", "Tabela auto 2026.pdf"]
    assert found.page is not None and found.end_page is not None
    assert found.page <= 137 <= found.end_page
    assert found.kind == "file" and found.anchor is None
    assert found.block_id == found.block_ids[0]
    assert found.highlight is not None
    assert "Bradesco/Auto/Tabela auto 2026.pdf" in result.looked_in


async def test_trashed_nodes_never_appear_and_an_unindexed_pdf_is_routed_by_its_title(env: Env) -> None:
    await env.search()

    options = env.options()
    assert not any("Tabela antiga" in option for option in options)
    assert any(option.split("\n")[0] == "Contrato novo.pdf" for option in options)


async def test_every_jev_call_of_a_search_is_logged_with_the_run(env: Env) -> None:
    run_id = uuid7()

    await env.search(run_id)

    logged = await env.uow.decisions.of_run(run_id)
    assert len(logged) == sum(len(questions) for _, questions in env.decider.calls)
    assert {decision.step for decision in logged} == {"route", "evidence"}
