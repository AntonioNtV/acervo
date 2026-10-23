"""The MCP server external agents connect to: Streamable HTTP at `/mcp`, `Authorization: Bearer <agent token>`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.http import StarletteWithLifespan
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from acervo.api.deps import get_event_bus, get_job_queue, get_storage
from acervo.core.errors import AcervoError, AuthError
from acervo.schemas.agent import AgentRead
from acervo.schemas.common import ErrorResponse
from acervo.schemas.proposal import ProposalRead
from acervo.services import agent_tools
from acervo.services.agent_tools import AgentTools, Filed, Folder, PageContent, PdfPages
from acervo.services.events import EventBus, JobQueue
from acervo.services.storage import Storage

CALLER = "acervo.caller"

server = FastMCP(
    "Acervo",
    instructions="A knowledge base of folders, Markdown pages and PDFs. Read with list_folder, read_page and "
    "read_pdf_pages. Every change is a proposal: the person approves it, unless this agent is set to approve "
    "automatically; each write tool answers whether its proposals were applied or wait.",
    mask_error_details=True,
)


@dataclass(frozen=True)
class _Caller:
    agent: AgentRead
    session_factory: async_sessionmaker[AsyncSession]
    storage: Storage
    jobs: JobQueue
    events: EventBus


@asynccontextmanager
async def _tools() -> AsyncIterator[AgentTools]:
    caller: _Caller = get_http_request().scope[CALLER]
    try:
        async with agent_tools.open_tools(
            caller.agent, caller.session_factory, caller.storage, caller.jobs, caller.events
        ) as tools:
            yield tools
    except AcervoError as exc:
        raise ToolError(exc.message) from exc


@server.tool
async def list_folder(
    node_id: Annotated[UUID | None, Field(description="A folder or page; omitted for the base's root.")] = None,
) -> Folder:
    """What is right under a folder or page: each child's kind, title and description."""
    async with _tools() as tools:
        return await tools.list_folder(node_id)


@server.tool
async def read_page(
    node_id: Annotated[UUID, Field(description="The page.")],
    section: Annotated[str | None, Field(description="A section's anchor or heading; omitted for all.")] = None,
) -> PageContent:
    """A page's Markdown as the person last typed it, whole or one `##` section."""
    async with _tools() as tools:
        return await tools.read_page(node_id, section)


@server.tool
async def read_pdf_pages(
    node_id: Annotated[UUID, Field(description="The PDF.")],
    first: Annotated[int, Field(description="The first page, counted from 1.")],
    last: Annotated[int, Field(description=f"The last page; at most {agent_tools.MAX_PDF_PAGES} pages a call.")],
) -> PdfPages:
    """The text of a range of pages of a PDF, read from the original file."""
    async with _tools() as tools:
        return await tools.read_pdf_pages(node_id, first, last)


@server.tool
async def remember(text: Annotated[str, Field(description="What was learned, in plain words.")]) -> Filed:
    """Files a fact in the right page and section, as a proposal; waits for it to be made."""
    async with _tools() as tools:
        return await tools.remember(text)


@server.tool
async def save_file(
    name: Annotated[str, Field(description="The file's name, ending in .pdf.")],
    content_base64: Annotated[str, Field(description="The file's bytes in base64.")],
) -> Filed:
    """Saves a PDF in the right folder, or as a new version of one already there, as a proposal."""
    async with _tools() as tools:
        return await tools.save_file(name, content_base64)


@server.tool
async def edit_section(
    node_id: Annotated[UUID, Field(description="The page.")],
    section: Annotated[str, Field(description="The section's anchor or heading.")],
    new_text: Annotated[str, Field(description="The section's new text under its heading.")],
) -> ProposalRead:
    """Proposes a section's new text."""
    async with _tools() as tools:
        return await tools.edit_section(node_id, section, new_text)


@server.tool
async def move(
    node_id: Annotated[UUID, Field(description="What to move.")],
    parent_id: Annotated[UUID | None, Field(description="The folder or page it goes under; null for the root.")],
) -> ProposalRead:
    """Proposes moving a folder, page or file."""
    async with _tools() as tools:
        return await tools.move(node_id, parent_id)


@server.tool
async def rename(
    node_id: Annotated[UUID, Field(description="What to rename.")],
    title: Annotated[str, Field(description="The new title.")],
) -> ProposalRead:
    """Proposes a new title for a folder, page or file."""
    async with _tools() as tools:
        return await tools.rename(node_id, title)


@server.tool
async def get_reply(
    reply_id: Annotated[UUID, Field(description="The reply_id a remember or save_file returned.")],
) -> Filed:
    """Where a remember or save_file stands now: still working, done with its proposals, or failed."""
    async with _tools() as tools:
        return await tools.get_reply(reply_id)


@server.tool
async def get_proposal(proposal_id: Annotated[UUID, Field(description="The proposal.")]) -> ProposalRead:
    """How a proposal stands: pending, applied, rejected or stale."""
    async with _tools() as tools:
        return await tools.get_proposal(proposal_id)


class _Door:
    """Lets a request in only with a live agent's token, and hands the tools that agent and the app's ports."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        try:
            if scheme.lower() != "bearer" or not token:
                raise AuthError("Missing or invalid agent token.")
            agent = await agent_tools.authenticate(request.app.state.session_factory, token.strip())
        except AuthError as exc:
            body = ErrorResponse(error=exc.code, message=exc.message, details={})
            refused = JSONResponse(body.model_dump(mode="json"), 401, headers={"WWW-Authenticate": "Bearer"})
            await refused(scope, receive, send)
            return
        scope[CALLER] = _Caller(
            agent,
            request.app.state.session_factory,
            get_storage(request),
            get_job_queue(request),
            get_event_bus(request),
        )
        await request.app.state.mcp(scope, receive, send)


async def _serve(http: StarletteWithLifespan, started: asyncio.Event, stop: asyncio.Event) -> None:
    async with http.lifespan(http):
        started.set()
        await stop.wait()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One per app: the session manager inside runs once.
    app.state.mcp = http = server.http_app(path="/mcp", stateless_http=True, json_response=True)
    started, stop = asyncio.Event(), asyncio.Event()
    # Its task group must close in the task that opened it, and a lifespan may start and end in different tasks (the
    # tests' fixtures do): it runs in a task of its own.
    serving = asyncio.create_task(_serve(http, started, stop))
    waiting = asyncio.create_task(started.wait())
    await asyncio.wait({serving, waiting}, return_when=asyncio.FIRST_COMPLETED)
    if serving.done():
        waiting.cancel()
        serving.result()
    try:
        yield
    finally:
        stop.set()
        await serving


router = APIRouter(tags=["mcp"], lifespan=_lifespan)
router.routes.append(Route("/mcp", _Door(), methods=["GET", "POST", "DELETE"], include_in_schema=False))
