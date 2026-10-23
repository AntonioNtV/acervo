from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings
from acervo.db.models import Agent, Proposal
from acervo.repositories.proposal import ProposalRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.proposal import CreatePagePayload, ProposalCreate
from acervo.services.events import RecordingJobQueue
from acervo.services.proposal_service import ProposalService
from acervo.services.storage import Storage


@pytest.fixture(autouse=True)
def jobs(app: FastAPI) -> RecordingJobQueue:
    app.state.job_queue = RecordingJobQueue()
    return app.state.job_queue  # type: ignore[no-any-return]


async def _proposal(client: httpx.AsyncClient, session: AsyncSession, parent: str | None = None) -> tuple[str, str]:
    """A base made through the API, and a new page proposed in it by its chat."""
    kb_id: str = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    chat = await session.scalar(select(Agent.id).where(Agent.kb_id == UUID(kb_id)))
    assert chat is not None
    parent_id = None
    if parent is not None:
        created = await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "folder", "title": parent})
        parent_id = UUID(created.json()["id"])
    payload = CreatePagePayload(parent_id=parent_id, parent_path=parent or "", title="Prazos", markdown="# Prazos\n")
    proposal = await ProposalRepository(session).create(
        ProposalCreate(kb_id=UUID(kb_id), agent_id=chat, payload=payload)
    )
    await session.flush()
    return kb_id, str(proposal.id)


async def _children(client: httpx.AsyncClient, kb_id: str) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = (await client.get(f"/v1/kbs/{kb_id}/children")).json()
    return children


async def test_list_pending_then_accept(client: httpx.AsyncClient, session: AsyncSession) -> None:
    kb_id, proposal_id = await _proposal(client, session)

    pending = (await client.get(f"/v1/kbs/{kb_id}/proposals", params={"status": "pending"})).json()
    assert [(p["id"], p["kind"], p["agent_name"]) for p in pending] == [(proposal_id, "create_page", "Chat do Acervo")]
    assert await _children(client, kb_id) == []

    response = await client.post(f"/v1/proposals/{proposal_id}/accept")

    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["accepted_by"]) == ("applied", "person")
    assert [child["title"] for child in await _children(client, kb_id)] == ["Prazos"]
    assert (await client.get(f"/v1/kbs/{kb_id}/proposals")).json() == []


async def test_accepting_a_new_page_refreshes_its_folder_description(
    client: httpx.AsyncClient, session: AsyncSession, jobs: RecordingJobQueue
) -> None:
    kb_id, proposal_id = await _proposal(client, session, parent="Bradesco")
    folder = (await _children(client, kb_id))[0]["id"]

    await client.post(f"/v1/proposals/{proposal_id}/accept")

    assert jobs.jobs == [("refresh_descriptions", {"node_ids": [folder]})]


async def test_reject_without_a_reason_is_422(client: httpx.AsyncClient, session: AsyncSession) -> None:
    kb_id, proposal_id = await _proposal(client, session)

    refused = await client.post(f"/v1/proposals/{proposal_id}/reject", json={})
    rejected = await client.post(f"/v1/proposals/{proposal_id}/reject", json={"reason": "already_there"})

    assert (refused.status_code, refused.json()["error"]) == (422, "validation")
    assert rejected.status_code == 200, rejected.text
    assert (rejected.json()["status"], rejected.json()["reject_reason"]) == ("rejected", "already_there")
    assert (await client.get(f"/v1/proposals/{proposal_id}")).json()["status"] == "rejected"
    assert await _children(client, kb_id) == []


async def test_auto_applied_proposals_are_listed_with_their_agent(
    client: httpx.AsyncClient,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    kb_id, by_person = await _proposal(client, session)
    agent = (await client.post(f"/v1/kbs/{kb_id}/agents", json={"name": "Claude", "mode": "auto"})).json()
    async with UnitOfWork(session_factory) as uow:
        service = ProposalService(uow, Storage(test_settings))
        old, new = [
            await service.create(
                ProposalCreate(
                    kb_id=UUID(kb_id),
                    agent_id=agent["id"],
                    payload=CreatePagePayload(parent_id=None, parent_path="", title=title, markdown=f"# {title}\n"),
                )
            )
            for title in ("Antiga", "Vistoria")
        ]
    await session.execute(
        update(Proposal).where(Proposal.id == old.id).values(applied_at=datetime.now(UTC) - timedelta(days=8))
    )
    assert (await client.post(f"/v1/proposals/{by_person}/accept")).status_code == 200

    auto = (await client.get(f"/v1/kbs/{kb_id}/proposals", params={"status": "applied", "accepted_by": "auto"})).json()
    applied = (await client.get(f"/v1/kbs/{kb_id}/proposals", params={"status": "applied"})).json()

    assert [(p["id"], p["agent_name"], p["accepted_by"]) for p in auto] == [(str(new.id), "Claude", "auto")]
    assert [p["id"] for p in applied] == [by_person, str(new.id)]
    undone = await client.post(f"/v1/proposals/{new.id}/undo")
    assert (undone.status_code, undone.json()["status"]) == (201, "applied"), undone.text
