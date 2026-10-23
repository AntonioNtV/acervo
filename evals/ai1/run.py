"""AI-1's synthetic cases: each fact or PDF is filed through `FilingService` (the Curator the chat's tools and MCP
agents call) with the LLM decider, over a seeded base in a database and a bucket made for the run and dropped after it,
so no base of the developer's is ever touched.

    make eval-ai1
"""

import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import aioboto3
import pymupdf
from alembic import command
from alembic.config import Config
from pydantic import BaseModel, Field, TypeAdapter, model_validator
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.ids import uuid7
from acervo.core.settings import LlmRoles, Settings, Thresholds, get_settings
from acervo.db.session import async_url
from acervo.model_clients.decider import Decider
from acervo.model_clients.factory import build_decider, build_writer
from acervo.model_clients.writer import Writer
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.conversation import Attachment
from acervo.schemas.kb import KbCreate
from acervo.schemas.node import NodeAdd
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    DecisionLogRead,
    MovePayload,
    PatchPayload,
    ProposalPayload,
    RenamePayload,
    ReplacePdfPayload,
    SavePdfPayload,
    UndoPayload,
)
from acervo.services.base_service import BaseService
from acervo.services.file_service import FileService
from acervo.services.filing_service import Filing, FilingService, Origin
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
PDF = "application/pdf"
OUTCOME = {
    "append": "append",
    "edit": "edit",
    "create_page": "create",
    "conflict": "conflict",
    "save_pdf": "save",
    "replace_pdf": "replace",
}
# PydanticAI reads each provider's key from the environment; a provider missing here is not checked.
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cohere": "CO_API_KEY",
    "huggingface": "HF_TOKEN",
    "bedrock": "AWS_ACCESS_KEY_ID",
}

Outcome = Literal["append", "create", "conflict", "already", "not-sure", "save", "replace"]
Level = Literal["first", "second", "miss"]
# What the place of each outcome must be in the seed; append, conflict and already name a page or one of its sections.
WANTED = {
    "create": ("folder", "page", "root"),
    "save": ("folder", "root"),
    "replace": ("file",),
    "not-sure": ("folder", "page", "root"),
}


class GeneratedPdf(BaseModel):
    """A small PDF written for the run: one text per page and the outline's titles."""

    pages: list[str] = Field(min_length=1)
    outline: list[str] = []


type Folder = dict[str, str | GeneratedPdf | Folder]


class Base(BaseModel):
    """The seed: names ending in .md are pages with their Markdown, in .pdf generated PDFs, the rest folders."""

    name: str
    tree: Folder


class Expected(BaseModel):
    """What one part of the message should become. `place` is the page (› section) for append, conflict and already;
    the folder for create and save; the PDF for replace; for not-sure, a place the options should hold."""

    outcome: Outcome
    place: str | None = None


class Case(BaseModel):
    id: str
    message: str = ""
    files: dict[str, GeneratedPdf] = {}
    # More than one: one proposal per file.
    expect: list[Expected] = Field(min_length=1)

    @model_validator(mode="after")
    def _something_sent(self) -> "Case":
        if not self.message.strip() and not self.files:
            raise ValueError(f"{self.id}: a case needs a message or a file")
        return self


@dataclass(frozen=True)
class Seen:
    """One outcome of the reply, its place and the other places it offered."""

    outcome: str
    place: str
    others: tuple[str, ...] = ()


@dataclass(frozen=True)
class Result:
    case: Case
    status: str
    seen: list[Seen]
    levels: list[Level]
    decisions: list[DecisionLogRead]

    @property
    def level(self) -> Level:
        return "miss" if "miss" in self.levels else "second" if "second" in self.levels else "first"


def load() -> tuple[Base, list[Case]]:
    base = Base.model_validate_json((HERE / "base.json").read_text())
    lines = (HERE / "cases.jsonl").read_text().splitlines()
    return base, TypeAdapter(list[Case]).validate_python([json.loads(line) for line in lines if line.strip()])


def seeded(base: Base) -> dict[str, str]:
    """Each path of the seed and its kind: folder, page, file, or section as "page › heading"."""
    kinds: dict[str, str] = {}

    def walk(folder: Folder, prefix: str) -> None:
        for name, value in folder.items():
            if isinstance(value, str):
                page = prefix + name.removesuffix(".md")
                kinds[page] = "page"
                headings = (line.removeprefix("## ").strip() for line in value.splitlines() if line.startswith("## "))
                kinds.update({f"{page} › {heading}": "section" for heading in headings})
            elif isinstance(value, GeneratedPdf):
                kinds[prefix + name] = "file"
            else:
                kinds[prefix + name] = "folder"
                walk(value, f"{prefix}{name}/")

    walk(base.tree, "")
    return kinds


def check(base: Base, cases: list[Case]) -> list[str]:
    """What in the cases does not match the seed; the runner refuses to run while anything is listed."""
    kinds = seeded(base)
    problems: list[str] = []
    ids = Counter(case.id for case in cases)
    problems += [f"{id}: the id is repeated" for id, count in ids.items() if count > 1]
    for case in cases:
        problems += [f"{case.id}: {name} is not a .pdf" for name in case.files if not name.endswith(".pdf")]
        for expected in case.expect:
            problem = _misplaced(expected, kinds)
            if problem:
                problems.append(f"{case.id}: {problem}")
    return problems


def _misplaced(expected: Expected, kinds: dict[str, str]) -> str | None:
    place, outcome = expected.place, expected.outcome
    if place is None:
        return None if outcome == "not-sure" else f"{outcome} needs a place"
    wanted = WANTED.get(outcome, ("page", "section"))
    if kinds.get(place) in wanted or place == "" and "root" in wanted:
        return None
    return f"{place!r} is not a {' or '.join(wanted)} of the base"


def pdf_bytes(pdf: GeneratedPdf) -> bytes:
    document = pymupdf.open()
    for page_text in pdf.pages:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 523, 770), page_text, fontsize=11)
    if pdf.outline:
        document.set_toc([[1, title, min(index + 1, len(pdf.pages))] for index, title in enumerate(pdf.outline)])
    data: bytes = document.tobytes()
    document.close()
    return data


async def _seed(uow: UnitOfWork, storage: Storage, base: Base) -> uuid.UUID:
    kb = await BaseService(uow).create(KbCreate(name=base.name))
    tree, files = TreeService(uow), FileService(uow, storage)

    async def add(folder: Folder, parent_id: uuid.UUID | None) -> None:
        for name, value in folder.items():
            if isinstance(value, GeneratedPdf):
                await files.save(kb.id, parent_id, name, BytesIO(pdf_bytes(value)))
            elif isinstance(value, str):
                page = NodeAdd(parent_id=parent_id, kind="page", title=name.removesuffix(".md"))
                await tree.create(kb.id, page, markdown=value)
            else:
                node = await tree.create(kb.id, NodeAdd(parent_id=parent_id, kind="folder", title=name))
                await add(value, node.id)

    await add(base.tree, None)
    return kb.id


def _place(payload: ProposalPayload) -> str:
    match payload:
        case PatchPayload() | ConflictPayload():
            return f"{payload.path} › {payload.heading}" if payload.heading else payload.path
        case CreatePagePayload() | SavePdfPayload():
            return payload.parent_path
        case MovePayload():
            return f"{payload.from_path} → {payload.to_path}"
        case RenamePayload():
            return f"{payload.path} → {payload.title}"
        case ReplacePdfPayload() | UndoPayload():
            return payload.path


def seen(filings: list[Filing]) -> list[Seen]:
    """What each input became, in order, with the other places it offered."""
    outcomes: list[Seen] = []
    for filing in filings:
        if filing.written is not None:
            written = filing.written
            outcomes.append(Seen("already", f"{written.path} › {written.heading}" if written.heading else written.path))
            continue
        assert filing.proposal is not None
        proposal = filing.proposal
        others = tuple(option.path for option in proposal.alternatives or [])
        if filing.placed:
            outcomes.append(Seen(OUTCOME[proposal.kind], _place(proposal.payload), others))
        else:
            outcomes.append(Seen("not-sure", others[0] if others else "", others[1:]))
    return outcomes


async def _staged(storage: Storage, kb_id: uuid.UUID, name: str, pdf: GeneratedPdf) -> Attachment:
    """A PDF as the chat stages a dropped one: in storage, outside the base."""
    data = pdf_bytes(pdf)
    sha256 = hashlib.sha256(data).hexdigest()
    key = f"staged/{kb_id}/{sha256}"
    await storage.put(key, BytesIO(data), len(data))
    return Attachment(storage_key=key, sha256=sha256, size=len(data), name=name, mime=PDF)


def _at(expected: str, place: str) -> bool:
    """A place without a section matches any section of its page."""
    return place == expected or place.startswith(f"{expected} › ")


def score(expected: Expected, outcomes: list[Seen]) -> Level:
    level: Level = "miss"
    for outcome in outcomes:
        if outcome.outcome != expected.outcome:
            continue
        if expected.place is None or _at(expected.place, outcome.place):
            return "first"
        if expected.place.split(" › ")[0] in outcome.others:
            level = "second"
    return level


async def run(
    session_factory: async_sessionmaker[AsyncSession],
    storage: Storage,
    decider: Decider,
    writer: Writer,
    thresholds: Thresholds,
    base: Base,
    cases: list[Case],
) -> list[Result]:
    """Seeds the base, then files each case, in order, as the built-in chat's tools do."""
    results: list[Result] = []
    async with UnitOfWork(session_factory) as uow:
        kb_id = await _seed(uow, storage, base)
        agent = await uow.agents.get_by(kb_id=kb_id, built_in=True)
        assert agent is not None
        filing = FilingService(uow, storage, decider, writer, thresholds)
        for case in cases:
            origin = Origin(agent, uuid7())
            try:
                if case.files:
                    staged = [await _staged(storage, kb_id, name, pdf) for name, pdf in case.files.items()]
                    filings = [await filing.attachment(attachment, origin) for attachment in staged]
                else:
                    filings = [await filing.fact(case.message, origin)]
                status, outcomes = "done", seen(filings)
            except Exception as exc:
                status, outcomes = "failed", [Seen("failed", str(exc))]
            decisions = await uow.decisions.of_run(origin.run_id)
            levels = [score(expected, outcomes) for expected in case.expect]
            results.append(Result(case, status, outcomes, levels, decisions))
    return results


def _top(decision: DecisionLogRead) -> str:
    index = max(range(len(decision.probs)), key=decision.probs.__getitem__)
    option = decision.options[index]
    return f"{decision.step} {option[:32] + '…' if len(option) > 32 else option} {decision.probs[index]:.2f}"


def report(results: list[Result], decider: str) -> str:
    lines = [f"AI-1 synthetic cases · decider {decider} · {len(results)} cases", ""]
    for number, result in enumerate(results, 1):
        lines.append(f"{number:02d} {result.case.id} · {result.level}")
        for expected, level in zip(result.case.expect, result.levels, strict=True):
            lines.append(f"   expected {expected.outcome} {expected.place or ''} · {level}".rstrip())
        for outcome in result.seen:
            others = f" (also {', '.join(outcome.others)})" if outcome.others else ""
            lines.append(f"   got      {outcome.outcome} {outcome.place}{others}".rstrip())
        lines += [f"   {'top' if i == 0 else '':<8} {_top(d)}" for i, d in enumerate(result.decisions)]
    totals: dict[str, Counter[Level]] = {}
    for result in results:
        for expected, level in zip(result.case.expect, result.levels, strict=True):
            totals.setdefault(expected.outcome, Counter())[level] += 1
    lines += ["", f"{'kind':<10} {'first':>5} {'second':>6} {'miss':>4}"]
    for kind, counts in totals.items():
        lines.append(f"{kind:<10} {counts['first']:>5} {counts['second']:>6} {counts['miss']:>4}")
    first = sum(result.level == "first" for result in results)
    second = sum(result.level == "second" for result in results)
    total = len(results)
    lines.append(f"\nright place, first path: {first}/{total} · first or second: {first + second}/{total}")
    return "\n".join(lines)


def missing_keys(roles: LlmRoles) -> list[str]:
    providers = {model.split(":", 1)[0] for model in roles.model_dump().values()}
    return sorted(key for p in providers if (key := PROVIDER_KEYS.get(p)) and not os.environ.get(key))


def _s3(settings: Settings) -> Any:
    return aioboto3.Session().client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


async def _admin(settings: Settings, sql: str) -> None:
    engine = create_async_engine(async_url(settings.database_url), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


async def _bucket(settings: Settings, create: bool) -> None:
    async with _s3(settings) as s3:
        if create:
            await s3.create_bucket(Bucket=settings.s3_bucket)
            return
        async for page in s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_bucket):
            for item in page.get("Contents", []):
                await s3.delete_object(Bucket=settings.s3_bucket, Key=item["Key"])
        await s3.delete_bucket(Bucket=settings.s3_bucket)


async def _run_throwaway(settings: Settings, base: Base, cases: list[Case]) -> list[Result]:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        decider, writer = build_decider(settings), build_writer(settings)
        return await run(factory, Storage(settings), decider, writer, settings.thresholds, base, cases)
    finally:
        await engine.dispose()


def main() -> int:
    settings = get_settings().model_copy(update={"decider": "llm"})
    if missing := missing_keys(settings.llm_roles):
        print(f"skipped: the AI-1 cases call the LLM; set {', '.join(missing)} to run them")
        return 0
    base, cases = load()
    if problems := check(base, cases):
        print("\n".join(problems))
        return 1
    suffix = uuid.uuid4().hex[:12]
    database = f"acervo_evals_{suffix}"
    url = make_url(async_url(settings.database_url)).set(database=database).render_as_string(hide_password=False)
    throwaway = settings.model_copy(update={"database_url": url, "s3_bucket": f"acervo-evals-{suffix}"})
    asyncio.run(_admin(settings, f'create database "{database}"'))
    try:
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        asyncio.run(_bucket(throwaway, create=True))
        try:
            results = asyncio.run(_run_throwaway(throwaway, base, cases))
        finally:
            asyncio.run(_bucket(throwaway, create=False))
    finally:
        asyncio.run(_admin(settings, f'drop database "{database}" with (force)'))
    print(report(results, settings.decider))
    return 0


if __name__ == "__main__":
    sys.exit(main())
