from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models import Agent
from acervo.repositories.proposal import ProposalRepository
from acervo.schemas.proposal import CreatePagePayload, ProposalCreate


async def _proposal(client: httpx.AsyncClient, session: AsyncSession) -> tuple[str, str]:
    """A base made through the API, and a new page proposed in it by its chat."""
    kb_id: str = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    chat = await session.scalar(select(Agent.id).where(Agent.kb_id == UUID(kb_id)))
    assert chat is not None
    payload = CreatePagePayload(parent_id=None, parent_path="", title="Prazos", markdown="# Prazos\n")
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


async def test_reject_without_a_reason_is_422(client: httpx.AsyncClient, session: AsyncSession) -> None:
    kb_id, proposal_id = await _proposal(client, session)

    refused = await client.post(f"/v1/proposals/{proposal_id}/reject", json={})
    rejected = await client.post(f"/v1/proposals/{proposal_id}/reject", json={"reason": "already_there"})

    assert (refused.status_code, refused.json()["error"]) == (422, "validation")
    assert rejected.status_code == 200, rejected.text
    assert (rejected.json()["status"], rejected.json()["reject_reason"]) == ("rejected", "already_there")
    assert (await client.get(f"/v1/proposals/{proposal_id}")).json()["status"] == "rejected"
    assert await _children(client, kb_id) == []
