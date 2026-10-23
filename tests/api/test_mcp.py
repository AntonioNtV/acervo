from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.db.models import PageVersion
from acervo.domain.decisions import Choice, Question
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.fakes import FakeDecider, FakeProbs, FakeWriter
from acervo.pipeline.index.markdown import index_markdown
from acervo.repositories.uow import UnitOfWork
from acervo.services.agent_tools import AgentTools
from acervo.services.chat_service import ChatService
from acervo.services.events import InMemoryEventBus, RecordingJobQueue

MakeTree = Callable[..., Awaitable[Any]]
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}, "Arquivo": None}
TO_THE_PAGE: dict[str, FakeProbs] = {
    "descent:": {"Bradesco (pasta) — Contém:\nResidencial": 1.0},
    "descent:Bradesco": {"Residencial (pasta) — Contém:\nEmissão de apólice": 1.0},
    "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 1.0},
    "covered": 0.1,
    "contradicts": 0.1,
    "section": {"Prazos": 1.0},
    "line": {"nenhuma linha": 1.0},
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
}


class RunningJobQueue(RecordingJobQueue):
    """Runs a message's job at once, as the worker would, with the fakes in place of Jev and the LLM; an agent's
    message is filed without the chat's model, so it is never called."""

    def __init__(self, app: FastAPI, decider: FakeDecider, writer: FakeWriter) -> None:
        super().__init__()
        self._app, self._decider, self._writer = app, decider, writer

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        await super().enqueue(job, **kwargs)
        if job != "handle_message":
            return
        state = self._app.state
        async with UnitOfWork(state.session_factory) as uow:
            never = ChatAgent("test")
            chat = ChatService(
                uow, state.storage, self._decider, self._writer, Thresholds(), state.event_bus, state.job_queue, never
            )
            await chat.handle(UUID(kwargs["message_id"]), UUID(kwargs["reply_id"]))


@pytest.fixture
def run_jobs(app: FastAPI, fake_decider: FakeDecider, fake_writer: FakeWriter) -> None:
    fake_decider.table.update(TO_THE_PAGE)
    app.state.event_bus = InMemoryEventBus()
    app.state.job_queue = RunningJobQueue(app, fake_decider, fake_writer)


def _mcp(app: FastAPI, token: str) -> Client[StreamableHttpTransport]:
    def http(**options: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test", **options)

    transport = StreamableHttpTransport(
        "http://api.test/mcp", headers={"Authorization": f"Bearer {token}"}, httpx_client_factory=http
    )
    return Client(transport)


async def _agent(client: httpx.AsyncClient, kb_id: UUID | str, mode: str = "ask") -> dict[str, Any]:
    created = await client.post(f"/v1/kbs/{kb_id}/agents", json={"name": "Claude", "mode": mode})
    assert created.status_code == 201, created.text
    agent: dict[str, Any] = created.json()
    return agent


async def _tree(make_tree: MakeTree, session: AsyncSession) -> Any:
    tree = await make_tree(TREE)
    version = await session.scalar(select(PageVersion).where(PageVersion.node_id == tree[PAGE].id))
    assert version is not None
    version.markdown = TEXT
    await session.flush()
    return tree


async def test_an_agent_lists_the_tools(app: FastAPI, client: httpx.AsyncClient) -> None:
    kb = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()
    agent = await _agent(client, kb["id"])

    async with _mcp(app, agent["token"]) as mcp:
        tools = {tool.name for tool in await mcp.list_tools()}

    assert tools == {
        "search",
        "fetch",
        "list_folder",
        "read_page",
        "read_pdf_pages",
        "remember",
        "save_file",
        "edit_section",
        "move",
        "rename",
        "get_reply",
        "get_proposal",
    }


async def test_no_invalid_or_revoked_token_is_refused(client: httpx.AsyncClient) -> None:
    kb = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()
    agent = await _agent(client, kb["id"])
    revoked = await _agent(client, kb["id"])
    assert (await client.delete(f"/v1/agents/{revoked['id']}")).status_code == 200
    accept = {"Accept": "application/json, text/event-stream"}

    for authorization in (None, "Bearer acv_not-a-token", f"Bearer {revoked['token']}", agent["token"]):
        headers = accept if authorization is None else {**accept, "Authorization": authorization}
        refused = await client.post("/mcp", json=INITIALIZE, headers=headers)
        assert (refused.status_code, refused.json()["error"]) == (401, "unauthorized"), authorization

    let_in = await client.post("/mcp", json=INITIALIZE, headers={**accept, "Authorization": f"Bearer {agent['token']}"})
    assert let_in.status_code == 200, let_in.text


async def test_another_base_is_unreachable(
    app: FastAPI, client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession
) -> None:
    other = await _tree(make_tree, session)
    kb = (await client.post("/v1/kbs", json={"name": "Outra base"})).json()
    agent = await _agent(client, kb["id"])

    async with _mcp(app, agent["token"]) as mcp:
        root = await mcp.call_tool("list_folder", {})
        assert root.structured_content == {"node_id": None, "path": "", "children": []}
        # Each tool's scoping is in tests/services/test_agent_tools.py; here, that it reaches the agent as an error.
        with pytest.raises(ToolError, match="not found"):
            await mcp.call_tool("read_page", {"node_id": str(other[PAGE].id)})


@pytest.mark.usefixtures("run_jobs")
async def test_remember_waits_in_ask_mode_and_is_applied_in_auto_mode(
    app: FastAPI, client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await _tree(make_tree, session)
    agent = await _agent(client, tree.kb.id)

    async with _mcp(app, agent["token"]) as mcp:
        asked = (await mcp.call_tool("remember", {"text": "O prazo de emissão é de 5 dias úteis."})).structured_content
        assert asked is not None and asked["status"] == "done"
        [pending] = asked["proposals"]
        assert (pending["kind"], pending["status"], pending["agent_id"]) == ("append", "pending", agent["id"])

        assert (await client.patch(f"/v1/agents/{agent['id']}", json={"mode": "auto"})).status_code == 200
        auto = (await mcp.call_tool("remember", {"text": "A vistoria é feita em 2 dias."})).structured_content
        assert auto is not None
        [applied] = auto["proposals"]
        assert (applied["status"], applied["accepted_by"]) == ("applied", "auto")

        stands = (await mcp.call_tool("get_proposal", {"proposal_id": pending["id"]})).structured_content
        assert stands is not None and stands["status"] == "pending"

    page = (await client.get(f"/v1/pages/{tree[PAGE].id}")).json()
    assert page["markdown"].count("- Uma nota") == 1


async def test_read_page_cuts_the_working_text_first(
    app: FastAPI, client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await _tree(make_tree, session)
    agent = await _agent(client, tree.kb.id)
    typed = TEXT + "\n## Vistoria\nDois dias.\n"
    saved = await client.put(f"/v1/pages/{tree[PAGE].id}/text", json={"markdown": typed, "revision": 0})
    assert saved.status_code == 200, saved.text

    async with _mcp(app, agent["token"]) as mcp:
        read = (await mcp.call_tool("read_page", {"node_id": str(tree[PAGE].id)})).structured_content

    assert read is not None and read["markdown"] == typed
    assert [section["anchor"] for section in read["sections"]] == ["documentos", "prazos", "vistoria"]
    versions = (await client.get(f"/v1/pages/{tree[PAGE].id}/versions")).json()
    assert versions[0]["id"] == read["version_id"] and len(versions) == 2


def _every_branch_finds_the_deadline(state: str, question: Question) -> FakeProbs:
    if isinstance(question, Choice):
        return [1.0] * (len(question.options) - 1) + [0.0]
    return 3.0 if "Cinco dias." in question.question else 0.0


async def test_search_gives_what_the_tools_give_and_fetch_reads_the_evidence_section(
    app: FastAPI, client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession, fake_decider: FakeDecider
) -> None:
    tree = await _tree(make_tree, session)
    agent = await _agent(client, tree.kb.id)
    fake_decider.answer = _every_branch_finds_the_deadline
    app.state.decider = fake_decider
    query = "Qual o prazo de emissão de apólice?"
    async with UnitOfWork(app.state.session_factory) as uow:
        await uow.indexes.start(tree[PAGE].id, "v1")
        await uow.indexes.finish(tree[PAGE].id, "v1", index_markdown(TEXT, RetrievalLimits()))
        await uow.commit()
        tools = AgentTools(
            uow, app.state.storage, RecordingJobQueue(), InMemoryEventBus(), await uow.agents.get(UUID(agent["id"]))
        )
        direct = await tools.search(query, fake_decider)

    async with _mcp(app, agent["token"]) as mcp:
        searched = (await mcp.call_tool("search", {"query": query})).structured_content
        assert searched is not None
        [evidence] = searched["evidence"]
        fetched = (await mcp.call_tool("fetch", {"ref": evidence["ref"]})).structured_content

    assert searched["evidence"] == [found.model_dump(mode="json") for found in direct.evidence]
    assert (evidence["path"], evidence["anchor"], evidence["kind"]) == (
        [*PAGE.removesuffix(".md").split("/")],
        "prazos",
        "page",
    )
    assert fetched is not None
    assert (fetched["section"], fetched["text"]) == ("prazos", "## Prazos\nCinco dias.\n")
