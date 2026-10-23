import asyncio
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from acervo.core.settings import Settings
from acervo.schemas.events import DoneEvent, StepEvent
from acervo.services.events import InMemoryEventBus, RecordingJobQueue
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
    assert jobs.jobs == [
        ("handle_message", {"message_id": messages[0]["id"], "reply_id": messages[1]["id"], "route": None})
    ]
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


async def test_events_stream_in_order(
    client: httpx.AsyncClient, jobs: RecordingJobQueue, bus: InMemoryEventBus
) -> None:
    _, conversation_id = await _conversation(client)
    stream = asyncio.create_task(client.get(f"/v1/conversations/{conversation_id}/events"))
    for _ in range(1000):
        if bus.subscribers(uuid.UUID(conversation_id)):
            break
        await asyncio.sleep(0.01)

    posted = await client.post(f"/v1/conversations/{conversation_id}/messages", data={"text": "Anota isso"})
    reply_id = uuid.UUID(posted.json()["reply"]["id"])
    await bus.publish(uuid.UUID(conversation_id), StepEvent(message_id=reply_id, step="choosing_place"))
    await bus.publish(uuid.UUID(conversation_id), DoneEvent(message_id=reply_id))
    await bus.close(uuid.UUID(conversation_id))
    response = await stream

    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    events: list[dict[str, Any]] = [
        json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert [(event["type"], event.get("message", {}).get("role")) for event in events] == [
        ("message", "person"),
        ("message", "acervo"),
        ("step", None),
        ("done", None),
    ]
    assert (await client.get(f"/v1/conversations/{uuid.uuid4()}/events")).status_code == 404
