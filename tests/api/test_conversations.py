import asyncio
import hashlib
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.settings import Settings
from acervo.db.models import Message
from acervo.repositories.proposal import ProposalRepository
from acervo.schemas.proposal import CreatePagePayload, ProposalCreate
from acervo.services.events import DONE, InMemoryEventBus, RecordingJobQueue
from acervo.services.storage import Storage

SIMPLE = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"


@pytest.fixture
def jobs(app: FastAPI) -> RecordingJobQueue:
    app.state.job_queue = RecordingJobQueue()
    return app.state.job_queue  # type: ignore[no-any-return]


@pytest.fixture
def bus(app: FastAPI) -> InMemoryEventBus:
    app.state.event_bus = InMemoryEventBus()
    return app.state.event_bus  # type: ignore[no-any-return]


async def _conversation(client: httpx.AsyncClient) -> tuple[str, str]:
    kb = await client.post("/v1/kbs", json={"name": "Seguros · Operação"})
    assert kb.status_code == 201, kb.text
    created = await client.post(f"/v1/kbs/{kb.json()['id']}/conversations", json={})
    assert created.status_code == 201, created.text
    return kb.json()["id"], created.json()["id"]


async def test_post_stores_two_messages_and_enqueues_one_job(
    client: httpx.AsyncClient, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    kb_id, conversation_id = await _conversation(client)
    page_id = str(uuid.uuid4())

    posted = await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        data={"text": "O prazo de emissão da apólice residencial é 5 dias úteis.", "page_id": page_id},
    )

    assert posted.status_code == 201, posted.text
    messages = (await client.get(f"/v1/conversations/{conversation_id}/messages")).json()
    assert [(m["role"], m["status"]) for m in messages] == [("person", "done"), ("acervo", "working")]
    assert messages[0]["context"] == {"page_id": page_id, "selection": None}
    assert jobs.jobs == [("handle_message", {"message_id": messages[0]["id"], "reply_id": messages[1]["id"]})]
    listed = (await client.get(f"/v1/kbs/{kb_id}/conversations")).json()
    assert [c["title"] for c in listed] == ["O prazo de emissão da apólice residencial é 5 dias úteis."]


async def test_attached_pdf_is_staged_and_not_in_the_tree(
    client: httpx.AsyncClient, jobs: RecordingJobQueue, bus: InMemoryEventBus, test_settings: Settings
) -> None:
    kb_id, conversation_id = await _conversation(client)

    with SIMPLE.open("rb") as source:
        posted = await client.post(
            f"/v1/conversations/{conversation_id}/messages",
            files={"files": ("Condições Gerais 2026.pdf", source, "application/pdf")},
        )

    assert posted.status_code == 201, posted.text
    [attachment] = posted.json()["message"]["attachments"]
    sha256 = hashlib.sha256(SIMPLE.read_bytes()).hexdigest()
    assert attachment == {
        "storage_key": f"staged/{kb_id}/{sha256}",
        "sha256": sha256,
        "size": SIMPLE.stat().st_size,
        "name": "Condições Gerais 2026.pdf",
        "mime": "application/pdf",
    }
    stored = b"".join([chunk async for chunk in Storage(test_settings).stream(attachment["storage_key"])])
    assert stored == SIMPLE.read_bytes()
    assert (await client.get(f"/v1/kbs/{kb_id}/children")).json() == []
    assert (await client.get(f"/v1/kbs/{kb_id}/search", params={"q": "Condições"})).json() == []


START, TEXT, FINISH = '{"type":"start"}', '{"type":"text-delta","id":"t","delta":"Anotado."}', '{"type":"finish"}'


def _chunks(response: httpx.Response) -> list[str]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    blocks = response.text.split("\n\n")
    assert blocks[-1] == "" and all(block.startswith("data: ") for block in blocks[:-1])
    return [block.removeprefix("data: ") for block in blocks[:-1]]


async def _reply(client: httpx.AsyncClient, session: AsyncSession, status: str) -> tuple[str, str, uuid.UUID]:
    kb_id, conversation_id = await _conversation(client)
    posted = await client.post(f"/v1/conversations/{conversation_id}/messages", data={"text": "Anota isso"})
    reply_id = uuid.UUID(posted.json()["reply"]["id"])
    await session.execute(update(Message).where(Message.id == reply_id).values(status=status, text="Anotado."))
    return kb_id, conversation_id, reply_id


async def test_the_stream_replays_a_finished_reply_then_done(
    client: httpx.AsyncClient, session: AsyncSession, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    _, _, reply_id = await _reply(client, session, "done")
    for chunk in (START, TEXT, FINISH, DONE):
        await bus.publish(reply_id, chunk)

    assert _chunks(await client.get(f"/v1/messages/{reply_id}/stream")) == [START, TEXT, FINISH, DONE]
    assert (await client.get(f"/v1/messages/{uuid.uuid4()}/stream")).status_code == 404


async def test_the_stream_replays_then_follows_a_working_reply(
    client: httpx.AsyncClient, session: AsyncSession, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    _, _, reply_id = await _reply(client, session, "working")
    await bus.publish(reply_id, START)

    stream = asyncio.create_task(client.get(f"/v1/messages/{reply_id}/stream"))
    for _ in range(1000):
        if bus.followers(reply_id):
            break
        await asyncio.sleep(0.01)
    for chunk in (TEXT, FINISH, DONE):
        await bus.publish(reply_id, chunk)

    assert _chunks(await stream) == [START, TEXT, FINISH, DONE]


async def test_ui_messages_return_the_thread_with_proposals_and_citations(
    client: httpx.AsyncClient, session: AsyncSession, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    kb_id, conversation_id, reply_id = await _reply(client, session, "done")
    [conversation] = (await client.get(f"/v1/kbs/{kb_id}/conversations")).json()
    citation = {"marker": 1, "node_id": str(uuid.uuid4()), "kind": "file", "path": "Arquivo/CG.pdf"}
    citation |= {"anchor": None, "page": 3}
    await session.execute(
        update(Message).where(Message.id == reply_id).values(text="Anotado [1].", citations=[citation], grounded=True)
    )
    proposal = await ProposalRepository(session).create(
        ProposalCreate(
            kb_id=uuid.UUID(kb_id),
            agent_id=uuid.UUID(conversation["agent_id"]),
            conversation_id=uuid.UUID(conversation_id),
            message_id=reply_id,
            payload=CreatePagePayload(parent_id=None, parent_path="", title="Prazos", markdown="# Prazos\n"),
        )
    )
    await session.flush()

    response = await client.get(f"/v1/conversations/{conversation_id}/ui-messages")

    assert response.status_code == 200, response.text
    person, reply = response.json()
    assert (person["role"], person["parts"], person["metadata"]["status"]) == (
        "user",
        [{"type": "text", "text": "Anota isso"}],
        "done",
    )
    assert (reply["id"], reply["role"], reply["metadata"]["grounded"]) == (str(reply_id), "assistant", True)
    text, proposed, source = reply["parts"]
    assert text == {"type": "text", "text": "Anotado [1]."}
    assert (proposed["type"], proposed["id"], proposed["data"]["status"]) == (
        "data-proposal",
        str(proposal.id),
        "pending",
    )
    assert source == {
        "type": "source-document",
        "sourceId": "[1]",
        "mediaType": "application/pdf",
        "title": "Arquivo/CG.pdf",
        "providerMetadata": {"acervo": citation},
    }


async def test_a_deleted_conversation_leaves_the_list_and_keeps_its_proposals(
    client: httpx.AsyncClient, session: AsyncSession, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    kb_id, conversation_id = await _conversation(client)
    posted = await client.post(f"/v1/conversations/{conversation_id}/messages", data={"text": "Prazo: 5 dias."})
    working = await client.delete(f"/v1/conversations/{conversation_id}")
    [conversation] = (await client.get(f"/v1/kbs/{kb_id}/conversations")).json()
    reply_id = uuid.UUID(posted.json()["reply"]["id"])
    await session.execute(update(Message).where(Message.id == reply_id).values(status="done"))
    payload = CreatePagePayload(parent_id=None, parent_path="", title="Prazos", markdown="# Prazos\n")
    proposal = await ProposalRepository(session).create(
        ProposalCreate(
            kb_id=uuid.UUID(kb_id),
            agent_id=uuid.UUID(conversation["agent_id"]),
            conversation_id=uuid.UUID(conversation_id),
            message_id=reply_id,
            payload=payload,
        )
    )
    await session.flush()

    deleted = await client.delete(f"/v1/conversations/{conversation_id}")

    assert working.status_code == 409, working.text
    assert deleted.status_code == 200 and deleted.json()["deleted_at"] is not None, deleted.text
    assert (await client.get(f"/v1/kbs/{kb_id}/conversations")).json() == []
    assert (await client.get(f"/v1/conversations/{conversation_id}/messages")).status_code == 404
    pending = (await client.get(f"/v1/kbs/{kb_id}/proposals")).json()
    assert [p["id"] for p in pending] == [str(proposal.id)]
