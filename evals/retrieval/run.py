"""The retrieval eval: each question goes through `ChatService` as the person's message, with the configured chat
model and decider, over a seeded base in a database and a bucket made for the run and dropped after it. A case is
covered when the reply cites its reference (the node, and the PDF's page when given); a "not_found" case when the
reply cites nothing. The references are only read here, never shown to the chat.

    make eval-retrieval
"""

import asyncio
import json
import runpy
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal

import pymupdf
from alembic import command
from alembic.config import Config
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.settings import Settings, Thresholds, get_settings
from acervo.db.session import async_url
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.decider import Decider
from acervo.model_clients.factory import build_decider, build_writer
from acervo.model_clients.writer import Writer
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.conversation import Citation, ConversationStart
from acervo.schemas.kb import KbCreate
from acervo.schemas.node import NodeAdd
from acervo.services.base_service import BaseService
from acervo.services.chat_service import ChatService
from acervo.services.conversation_service import ConversationService
from acervo.services.events import DONE, InMemoryEventBus, RecordingJobQueue
from acervo.services.file_service import FileService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
# evals/ is not a package: the PDF builders and AI-1's throwaway database and bucket are loaded from their files.
BUILDERS = runpy.run_path(str(HERE / "pdfs.py"))["BUILDERS"]
AI1 = runpy.run_path(str(HERE.parent / "ai1" / "run.py"))

# A name ending in .md is a page with its Markdown, in .pdf a PDF named by its builder in `pdfs.py`, else a folder.
type Folder = dict[str, str | Folder]


class Base(BaseModel):
    name: str
    tree: Folder


class Reference(BaseModel):
    """The page or PDF the answer must cite: its path as the chat cites it, and the PDF's page when it matters."""

    node: str
    page: int | None = None


class Case(BaseModel):
    id: str
    question: str
    # A follow-up: asked in the conversation of that earlier case.
    after: str | None = None
    expect: Reference | Literal["not_found"]


class Result(BaseModel):
    case: Case
    status: str
    text: str
    citations: list[Citation]
    error: str | None
    # Seconds from handing the message to the chat to its first text chunk, and to the reply's end.
    first_text: float | None
    total: float

    @property
    def hit(self) -> bool:
        if self.case.expect == "not_found":
            return self.status == "done" and not self.citations
        reference = self.case.expect
        return any(c.path == reference.node and reference.page in (None, c.page) for c in self.citations)


class TimedBus(InMemoryEventBus):
    """Keeps when each reply's first text chunk was published."""

    def __init__(self) -> None:
        super().__init__()
        self.first_text: dict[uuid.UUID, float] = {}

    async def publish(self, reply_id: uuid.UUID, chunk: str) -> None:
        if reply_id not in self.first_text and chunk != DONE and json.loads(chunk)["type"] == "text-delta":
            self.first_text[reply_id] = time.perf_counter()
        await super().publish(reply_id, chunk)


def load() -> tuple[Base, list[Case]]:
    base = Base.model_validate_json((HERE / "base.json").read_text())
    lines = (HERE / "cases.jsonl").read_text().splitlines()
    return base, TypeAdapter(list[Case]).validate_python([json.loads(line) for line in lines if line.strip()])


def seeded(base: Base) -> dict[str, int | None]:
    """Each page's path (None) and each PDF's path with its page count; folders are not references."""
    places: dict[str, int | None] = {}

    def walk(folder: Folder, prefix: str) -> None:
        for name, value in folder.items():
            if isinstance(value, dict):
                walk(value, f"{prefix}{name}/")
            elif name.endswith(".pdf"):
                places[prefix + name] = pymupdf.open(stream=BUILDERS[value]()).page_count if value in BUILDERS else 0
            else:
                places[prefix + name.removesuffix(".md")] = None

    walk(base.tree, "")
    return places


def check(base: Base, cases: list[Case]) -> list[str]:
    """What in the cases does not match the seed; the runner refuses to run while anything is listed."""
    places = seeded(base)
    problems = [f"{path}: no builder in pdfs.py" for path, pages in places.items() if pages == 0]
    problems += [f"{id}: the id is repeated" for id, count in Counter(case.id for case in cases).items() if count > 1]
    asked: set[str] = set()
    for case in cases:
        if case.after is not None and case.after not in asked:
            problems.append(f"{case.id}: follows {case.after!r}, which is not an earlier case")
        asked.add(case.id)
        if case.expect == "not_found":
            continue
        node, page = case.expect.node, case.expect.page
        if node not in places:
            problems.append(f"{case.id}: {node!r} is not a page or PDF of the base")
        elif page is not None and not 1 <= page <= (places[node] or 0):
            problems.append(f"{case.id}: {node!r} has no page {page}")
    return problems


async def _seed(uow: UnitOfWork, storage: Storage, base: Base) -> uuid.UUID:
    kb = await BaseService(uow).create(KbCreate(name=base.name))
    tree, files = TreeService(uow), FileService(uow, storage)

    async def add(folder: Folder, parent_id: uuid.UUID | None) -> None:
        for name, value in folder.items():
            if isinstance(value, dict):
                node = await tree.create(kb.id, NodeAdd(parent_id=parent_id, kind="folder", title=name))
                await add(value, node.id)
            elif name.endswith(".pdf"):
                await files.save(kb.id, parent_id, name, BytesIO(BUILDERS[value]()))
            else:
                await tree.create(kb.id, NodeAdd(parent_id=parent_id, kind="page", title=name[:-3]), markdown=value)

    await add(base.tree, None)
    return kb.id


async def run(
    session_factory: async_sessionmaker[AsyncSession],
    storage: Storage,
    decider: Decider,
    writer: Writer,
    thresholds: Thresholds,
    chat: ChatAgent,
    base: Base,
    cases: list[Case],
) -> list[Result]:
    """Seeds the base, then asks each case, in order, as the person does in the chat."""
    bus, jobs = TimedBus(), RecordingJobQueue()
    results: list[Result] = []
    async with UnitOfWork(session_factory) as uow:
        kb_id = await _seed(uow, storage, base)
        conversations = ConversationService(uow, storage, jobs, bus)
        service = ChatService(uow, storage, decider, writer, thresholds, bus, jobs, chat)
        threads: dict[str, uuid.UUID] = {}
        for case in cases:
            if case.after is None:
                threads[case.id] = (await conversations.create(kb_id, ConversationStart(title=case.id))).id
            else:
                threads[case.id] = threads[case.after]
            posted = await conversations.post(threads[case.id], case.question, [], None)
            start = time.perf_counter()
            reply = await service.handle(posted.message.id, posted.reply.id)
            total = time.perf_counter() - start
            first = bus.first_text.get(reply.id)
            results.append(
                Result(
                    case=case,
                    status=reply.status,
                    text=reply.text,
                    citations=reply.citations,
                    error=reply.error,
                    first_text=None if first is None else first - start,
                    total=total,
                )
            )
    return results


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20, method="inclusive")[-1] if len(values) > 1 else values[0]


def summary(results: list[Result]) -> dict[str, object]:
    answerable = [result for result in results if result.case.expect != "not_found"]
    unanswerable = [result for result in results if result.case.expect == "not_found"]
    firsts = [result.first_text for result in results if result.first_text is not None]
    totals = [result.total for result in results]
    return {
        "cases": len(results),
        "failed": sum(result.status != "done" for result in results),
        "coverage": f"{sum(r.hit for r in answerable)}/{len(answerable)}",
        "abstention": f"{sum(r.hit for r in unanswerable)}/{len(unanswerable)}",
        "first_text_median": round(statistics.median(firsts), 2) if firsts else None,
        "first_text_p95": round(_p95(firsts), 2) if firsts else None,
        "total_median": round(statistics.median(totals), 2) if totals else None,
        "total_p95": round(_p95(totals), 2) if totals else None,
    }


def report(results: list[Result], decider: str, chat: str) -> str:
    lines = [f"Retrieval eval · chat {chat} · decider {decider} · {len(results)} cases", ""]
    lines.append(f"{'case':<32} {'expected':<56} {'':<4} {'first':>6} {'total':>6}  cited")
    for result in results:
        expect = result.case.expect
        wanted = expect if expect == "not_found" else f"{expect.node}" + (f" p.{expect.page}" if expect.page else "")
        cited = ", ".join(f"{c.path}" + (f" p.{c.page}" if c.page else "") for c in result.citations)
        first = f"{result.first_text:.1f}" if result.first_text is not None else "-"
        mark = "ok" if result.hit else result.status if result.status != "done" else "miss"
        lines.append(f"{result.case.id:<32} {wanted[-56:]:<56} {mark:<4} {first:>6} {result.total:>6.1f}  {cited}")
    lines += ["", " · ".join(f"{key} {value}" for key, value in summary(results).items())]
    return "\n".join(lines)


def write(results: list[Result], decider: str, chat: str) -> Path:
    OUT.mkdir(exist_ok=True)
    # The reports stay out of git without an entry in the repository's .gitignore.
    (OUT / ".gitignore").write_text("*\n")
    path = OUT / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    runs = [result.model_dump(mode="json") | {"hit": result.hit} for result in results]
    data = {"chat": chat, "decider": decider, "summary": summary(results), "results": runs}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path


async def _run_throwaway(settings: Settings, base: Base, cases: list[Case]) -> list[Result]:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        decider, writer, chat = build_decider(settings), build_writer(settings), ChatAgent(settings.llm_roles.chat)
        return await run(factory, Storage(settings), decider, writer, settings.thresholds, chat, base, cases)
    finally:
        await engine.dispose()


def main() -> int:
    settings = get_settings()
    if missing := AI1["missing_keys"](settings.llm_roles):
        print(f"skipped: the retrieval eval calls the LLM; set {', '.join(missing)} to run it")
        return 0
    base, cases = load()
    if problems := check(base, cases):
        print("\n".join(problems))
        return 1
    suffix = uuid.uuid4().hex[:12]
    database = f"acervo_evals_{suffix}"
    url = make_url(async_url(settings.database_url)).set(database=database).render_as_string(hide_password=False)
    throwaway = settings.model_copy(update={"database_url": url, "s3_bucket": f"acervo-evals-{suffix}"})
    asyncio.run(AI1["_admin"](settings, f'create database "{database}"'))
    try:
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        asyncio.run(AI1["_bucket"](throwaway, create=True))
        try:
            results = asyncio.run(_run_throwaway(throwaway, base, cases))
        finally:
            asyncio.run(AI1["_bucket"](throwaway, create=False))
    finally:
        asyncio.run(AI1["_admin"](settings, f'drop database "{database}" with (force)'))
    print(report(results, settings.decider, settings.llm_roles.chat))
    print(f"\nreport: {write(results, settings.decider, settings.llm_roles.chat)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
